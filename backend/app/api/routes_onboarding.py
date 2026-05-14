"""Onboarding readiness and protocol setup routes."""

from __future__ import annotations

from dataclasses import asdict
import uuid
from typing import cast

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit.emitter import emit_standard_audit_event
from app.api.error_responses import raise_api_error
from app.api.schemas import (
    ApiErrorResponse,
    OrgLaunchReadinessResponse,
    OrgOnboardingStepUpdateRequest,
    ProtocolSetupStepResponse,
)
from app.core.deps import get_current_user
from app.db.models import User, UserOrg
from app.db.session import get_db
from app.onboarding.progress import STEP_DEFINITIONS
from app.onboarding.service import (
    collect_onboarding_signals,
    get_org_onboarding_readiness,
    get_protocol_setup_step,
    set_step_completion_override,
)
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability

router = APIRouter(prefix="/org/onboarding", tags=["onboarding"])


def _first_org_id(user_context) -> uuid.UUID:
    return user_context.org_ids[0]


def _require_onboarding_access(user: User, *, write: bool = False) -> None:
    capability = Capability.ONBOARDING_WRITE if write else Capability.READINESS_VIEW
    if not has_capability(cast(str | None, user.role), capability):
        raise_api_error(
            status_code=403,
            message="You do not have permission to access onboarding endpoints.",
            code="ACCESS_DENIED",
        )


def _to_readiness_response(readiness) -> OrgLaunchReadinessResponse:
    return OrgLaunchReadinessResponse.model_validate(
        {
            "org_id": readiness.org_id,
            "status": readiness.status,
            "percent_complete": readiness.percent_complete,
            "steps": [asdict(item) for item in readiness.steps],
            "blockers": [asdict(item) for item in readiness.blockers],
            "import_jobs": [asdict(item) for item in readiness.import_jobs],
            "integration_validations": [asdict(item) for item in readiness.integration_validations],
            "vehicle_qr_deployment": asdict(readiness.vehicle_qr_deployment)
            if readiness.vehicle_qr_deployment is not None
            else None,
            "test_incident_run": asdict(readiness.test_incident_run)
            if readiness.test_incident_run is not None
            else None,
            "latest_export_validation": asdict(readiness.latest_export_validation)
            if readiness.latest_export_validation is not None
            else None,
            "metrics": asdict(readiness.metrics) if readiness.metrics is not None else None,
            "alert_conditions": [asdict(item) for item in readiness.alert_conditions],
            "reporting_hooks": readiness.reporting_hooks,
            "snapshot_created_at_utc": readiness.snapshot_created_at_utc,
        }
    )


def _role_counts_for_org(db: Session, *, org_id: uuid.UUID) -> dict[str, int]:
    rows = (
        db.query(User.role)
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(UserOrg.org_id == org_id, User.is_active.is_(True))
        .all()
    )
    counts: dict[str, int] = {}
    for (role,) in rows:
        normalized = str(role or "").strip().lower()
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _role_violations(*, role_counts: dict[str, int]) -> list[str]:
    violations: list[str] = []
    if role_counts.get("org_admin", 0) < 1:
        violations.append("no org admin assigned")
    safety_capable_count = sum(
        count
        for role, count in role_counts.items()
        if has_capability(role, Capability.INCIDENT_WRITE)
    )
    if safety_capable_count < 1:
        violations.append("no safety manager assigned")
    return violations


@router.get(
    "/status",
    response_model=OrgLaunchReadinessResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Get organization onboarding readiness status",
)
def get_org_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_onboarding_access(current_user)
    context = build_user_auth_context(db, current_user)
    readiness = get_org_onboarding_readiness(db, org_id=_first_org_id(context))
    return _to_readiness_response(readiness)


@router.get(
    "/protocol-setup-step",
    response_model=ProtocolSetupStepResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Get protocol setup readiness details",
)
def get_org_onboarding_protocol_setup_step(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_onboarding_access(current_user)
    context = build_user_auth_context(db, current_user)
    step = get_protocol_setup_step(db, org_id=_first_org_id(context))
    return ProtocolSetupStepResponse.model_validate(asdict(step))


@router.post(
    "/mark-step",
    response_model=OrgLaunchReadinessResponse,
    responses={403: {"model": ApiErrorResponse}, 409: {"model": ApiErrorResponse}, 422: {"model": ApiErrorResponse}},
    summary="Mark onboarding checklist step as complete/incomplete",
)
def mark_org_onboarding_step(
    payload: OrgOnboardingStepUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_onboarding_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    valid_steps = {item.key for item in STEP_DEFINITIONS}
    if payload.step_key not in valid_steps:
        raise_api_error(status_code=422, message="Unknown step_key.", code="REQUEST_INVALID")
    if payload.step_key == "export_validation" and payload.completed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "export_validation_requires_test_export",
                "message": "Use /org/onboarding/export-check to complete export validation with a test export.",
            },
        )
    if payload.step_key == "users_roles" and payload.completed:
        signals = collect_onboarding_signals(db, org_id=org_id)
        if signals.org_admin_count < 1 or signals.safety_capable_user_count < 1:
            role_counts = _role_counts_for_org(db, org_id=org_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "users_roles_prerequisites_not_met",
                    "message": "Cannot complete users_roles step until role requirements are satisfied.",
                    "role_counts": role_counts,
                    "violations": _role_violations(role_counts=role_counts),
                },
            )
    set_step_completion_override(
        db,
        org_id=org_id,
        step_key=payload.step_key,
        is_completed=payload.completed,
        actor_user_id=cast(uuid.UUID, current_user.id),
        source=payload.source,
    )
    emit_standard_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="onboarding.step.override",
        event_type="onboarding_readiness_override_updated",
        entity_type="onboarding_step",
        entity_id=payload.step_key,
        outcome="success",
        metadata={"completed": payload.completed, "source": payload.source},
    )
    readiness = get_org_onboarding_readiness(db, org_id=org_id)
    return _to_readiness_response(readiness)
