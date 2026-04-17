"""Onboarding test incident run routes."""

from __future__ import annotations

from dataclasses import asdict
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit.emitter import emit_standard_audit_event
from app.api.error_responses import raise_api_error
from app.api.schemas import (
    ApiErrorResponse,
    OnboardingReadinessStepStatus,
    TestIncidentRunCreateRequest,
    TestIncidentRunResponse,
    TestIncidentRunsResponse,
    TestIncidentRunStepCompleteRequest,
)
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.onboarding.service import (
    complete_test_incident_run_step,
    create_test_incident_run,
    get_test_incident_run_by_id,
    list_test_incident_runs,
)
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability

router = APIRouter(prefix="/org/test-runs", tags=["test-runs"])


def _first_org_id(user_context) -> uuid.UUID:
    return user_context.org_ids[0]


def _require_test_run_access(user: User, *, write: bool = False) -> None:
    capability = Capability.INCIDENT_WRITE if write else Capability.INCIDENT_READ
    if not has_capability(user.role, capability):
        raise_api_error(
            status_code=403,
            message="You do not have permission to access test runs.",
            code="ACCESS_DENIED",
        )


def _to_test_run_response_row(row) -> TestIncidentRunResponse:
    return TestIncidentRunResponse(
        run_id=row.run_id,
        status=row.status,
        incident_id=row.incident_id,
        started_at_utc=row.started_at_utc,
        completed_at_utc=row.completed_at_utc,
        step_results=list(row.step_results_json or []),
        findings=list(row.findings_json or []),
    )


@router.post(
    "",
    response_model=TestIncidentRunResponse,
    status_code=201,
    responses={403: {"model": ApiErrorResponse}},
    summary="Create onboarding test incident run",
)
def create_org_test_run(
    payload: TestIncidentRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_test_run_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    run = create_test_incident_run(
        db,
        org_id=_first_org_id(context),
        actor_user_id=current_user.id,
        incident_id=payload.incident_id,
        findings=payload.findings,
    )
    emit_standard_audit_event(
        db,
        org_id=_first_org_id(context),
        actor_type="user",
        actor_id=str(current_user.id),
        action="onboarding.test_run.create",
        event_type="onboarding_test_run_created",
        entity_type="test_run",
        entity_id=str(run.run_id),
        outcome="success",
        metadata={"incident_id": str(payload.incident_id) if payload.incident_id else None},
    )
    return TestIncidentRunResponse.model_validate(asdict(run))


@router.get(
    "",
    response_model=TestIncidentRunsResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="List onboarding test runs",
)
def list_org_test_runs_route(
    status: OnboardingReadinessStepStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_test_run_access(current_user)
    context = build_user_auth_context(db, current_user)
    rows = list_test_incident_runs(db, org_id=_first_org_id(context))
    filtered = [_to_test_run_response_row(row) for row in rows if status is None or row.status == status]
    return TestIncidentRunsResponse(runs=filtered[offset : offset + limit])


@router.get(
    "/{run_id}",
    response_model=TestIncidentRunResponse,
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Get onboarding test run details",
)
def get_org_test_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_test_run_access(current_user)
    context = build_user_auth_context(db, current_user)
    row = get_test_incident_run_by_id(db, org_id=_first_org_id(context), run_id=run_id)
    if row is None:
        raise_api_error(status_code=404, message="Test run not found.", code="RESOURCE_NOT_FOUND")
    return _to_test_run_response_row(row)


@router.post(
    "/{run_id}/complete-step",
    response_model=TestIncidentRunResponse,
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Complete a step in onboarding test run",
)
def complete_org_test_run_step(
    run_id: uuid.UUID,
    payload: TestIncidentRunStepCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_test_run_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    try:
        run = complete_test_incident_run_step(
            db,
            org_id=_first_org_id(context),
            run_id=run_id,
            step_key=payload.step_key,
            step_status=payload.status,
            result=payload.result,
            source=payload.source,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "not_found":
            raise_api_error(status_code=404, message="Test run not found.", code="RESOURCE_NOT_FOUND")
        raise
    emit_standard_audit_event(
        db,
        org_id=_first_org_id(context),
        actor_type="user",
        actor_id=str(current_user.id),
        action="onboarding.test_run.complete_step",
        event_type="onboarding_test_run_step_completed",
        entity_type="test_run",
        entity_id=str(run_id),
        outcome="success",
        metadata={"step_key": payload.step_key, "step_status": payload.status},
    )
    return TestIncidentRunResponse.model_validate(asdict(run))
