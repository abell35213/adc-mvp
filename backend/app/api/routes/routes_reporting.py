"""Organization reporting routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    ReportAdoptionResponse,
    ReportEvidenceCompletenessResponse,
    ReportExportTurnaroundResponse,
    ReportIncidentOperationsResponse,
)
from app.commercial.enforcement import require_feature_enabled
from app.commercial.reporting import (
    FUTURE_REPORTING_FEATURES,
    PREMIUM_REPORTING_FEATURES,
    REPORT_ADOPTION_FEATURE,
    REPORT_EVIDENCE_COMPLETENESS_FEATURE,
    REPORT_EXPORT_TURNAROUND_FEATURE,
    REPORT_INCIDENT_OPERATIONS_FEATURE,
    query_adoption_report,
    query_evidence_completeness_report,
    query_export_turnaround_report,
    query_incident_operations_report,
)
from app.core.deps import require_workspace_view_permission
from app.db.models import User
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability

router = APIRouter(prefix="/org/reports", tags=["reporting"])


def _require_report_access(
    *,
    db: Session,
    org_id: uuid.UUID,
    current_user: User,
    feature_key: str,
) -> None:
    if not has_capability(current_user.role, Capability.REPORTING_BASIC_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permission to access reporting",
        )
    if feature_key in PREMIUM_REPORTING_FEATURES or feature_key in FUTURE_REPORTING_FEATURES:
        if not has_capability(current_user.role, Capability.REPORTING_PREMIUM_READ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission for premium reporting",
            )
    require_feature_enabled(
        db,
        org_id=org_id,
        actor_id=str(current_user.id),
        actor_role=str(current_user.role),
        feature_key=feature_key,
        action=f"reporting.{feature_key}.read",
        allow_internal_override=(
            feature_key in PREMIUM_REPORTING_FEATURES
            or feature_key in FUTURE_REPORTING_FEATURES
        ),
    )


@router.get("/adoption", response_model=ReportAdoptionResponse)
def get_adoption_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _require_report_access(
        db=db,
        org_id=org_id,
        current_user=current_user,
        feature_key=REPORT_ADOPTION_FEATURE,
    )
    return ReportAdoptionResponse(**query_adoption_report(db, org_ids=list(context.org_ids)))


@router.get("/incident-operations", response_model=ReportIncidentOperationsResponse)
def get_incident_operations_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _require_report_access(
        db=db,
        org_id=org_id,
        current_user=current_user,
        feature_key=REPORT_INCIDENT_OPERATIONS_FEATURE,
    )
    return ReportIncidentOperationsResponse(
        **query_incident_operations_report(db, org_ids=list(context.org_ids))
    )


@router.get("/export-turnaround", response_model=ReportExportTurnaroundResponse)
def get_export_turnaround_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _require_report_access(
        db=db,
        org_id=org_id,
        current_user=current_user,
        feature_key=REPORT_EXPORT_TURNAROUND_FEATURE,
    )
    return ReportExportTurnaroundResponse(
        **query_export_turnaround_report(db, org_ids=list(context.org_ids))
    )


@router.get("/evidence-completeness", response_model=ReportEvidenceCompletenessResponse)
def get_evidence_completeness_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _require_report_access(
        db=db,
        org_id=org_id,
        current_user=current_user,
        feature_key=REPORT_EVIDENCE_COMPLETENESS_FEATURE,
    )
    return ReportEvidenceCompletenessResponse(
        **query_evidence_completeness_report(db, org_ids=list(context.org_ids))
    )
