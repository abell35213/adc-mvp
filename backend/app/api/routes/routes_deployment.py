"""Deployment scope and expansion-readiness routes."""

from __future__ import annotations

from dataclasses import asdict
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.error_responses import raise_api_error
from app.api.schemas import (
    ApiErrorResponse,
    DeploymentProgressResponse,
    DeploymentScopeRequest,
    DeploymentScopeResponse,
    ExpansionReadinessResponse,
)
from app.audit.emitter import emit_standard_audit_event
from app.commercial.expansion import (
    get_deployment_progress,
    get_deployment_scope,
    get_expansion_readiness,
    set_deployment_scope,
)
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability

router = APIRouter(prefix="/org", tags=["deployment"])


def _first_org_id(user_context) -> uuid.UUID:
    return user_context.org_ids[0]


def _require_deployment_access(user: User, *, write: bool = False) -> None:
    capability = Capability.DEPLOYMENT_SCOPE_MANAGE if write else Capability.READINESS_VIEW
    if not has_capability(user.role, capability):
        raise_api_error(
            status_code=403,
            message="You do not have permission to access deployment scope endpoints.",
            code="ACCESS_DENIED",
        )


@router.get(
    "/deployment-scope",
    response_model=DeploymentScopeResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Get deployment scope",
)
def get_org_deployment_scope(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_deployment_access(current_user)
    context = build_user_auth_context(db, current_user)
    scope = get_deployment_scope(db, org_id=_first_org_id(context))
    return DeploymentScopeResponse.model_validate(asdict(scope))


@router.patch(
    "/deployment-scope",
    response_model=DeploymentScopeResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Update deployment scope",
)
def patch_org_deployment_scope(
    payload: DeploymentScopeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_deployment_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    scope = set_deployment_scope(
        db,
        org_id=org_id,
        scope=payload.scope,
        actor_user_id=current_user.id,
        targets=payload.targets,
        readiness_override=payload.readiness_override,
        source=payload.source,
    )
    emit_standard_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="deployment.scope.update",
        event_type="deployment_scope_updated",
        entity_type="deployment_scope",
        entity_id=scope.scope,
        outcome="success",
        metadata={
            "scope": scope.scope,
            "targets": scope.targets,
            "readiness_override": scope.readiness_override,
            "source": scope.source,
        },
    )
    return DeploymentScopeResponse.model_validate(asdict(scope))


@router.get(
    "/deployment-progress",
    response_model=DeploymentProgressResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Get deployment progress",
)
def get_org_deployment_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_deployment_access(current_user)
    context = build_user_auth_context(db, current_user)
    progress = get_deployment_progress(db, org_id=_first_org_id(context))
    return DeploymentProgressResponse.model_validate(asdict(progress))


@router.get(
    "/expansion-readiness",
    response_model=ExpansionReadinessResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Get expansion readiness",
)
def get_org_expansion_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_deployment_access(current_user)
    context = build_user_auth_context(db, current_user)
    readiness = get_expansion_readiness(db, org_id=_first_org_id(context))
    return ExpansionReadinessResponse.model_validate(asdict(readiness))
