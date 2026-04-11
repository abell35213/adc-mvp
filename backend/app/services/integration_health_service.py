"""Integration operation/evidence status tracking helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import EvidenceRequest, IntegrationOperation
from app.db.repo.integration_operation_status_history import create_operation_status_history


def transition_operation_status(
    db: Session,
    *,
    operation: IntegrationOperation,
    to_status: str,
    message: str | None = None,
):
    """Transition an operation status and write history."""
    from_status = operation.status
    operation.status = to_status
    if to_status == "running" and operation.started_at_utc is None:
        operation.started_at_utc = datetime.now(timezone.utc)
    if to_status in {"succeeded", "failed", "canceled"}:
        operation.completed_at_utc = datetime.now(timezone.utc)
    db.add(operation)
    db.commit()
    db.refresh(operation)

    create_operation_status_history(
        db,
        operation_id=operation.operation_id,
        org_id=operation.org_id,
        incident_id=operation.incident_id,
        provider=operation.provider,
        domain=operation.domain,
        from_status=from_status,
        to_status=to_status,
        correlation_id=operation.correlation_id,
        external_reference=operation.external_reference,
        message=message,
    )
    return operation


def set_evidence_request_status(
    db: Session,
    *,
    evidence_request: EvidenceRequest,
    status: str,
    response_payload_json: dict | None = None,
):
    """Update evidence request status and timestamps."""
    evidence_request.status = status
    if response_payload_json is not None:
        evidence_request.response_payload_json = response_payload_json
    if status == "fulfilled":
        evidence_request.fulfilled_at_utc = datetime.now(timezone.utc)
    db.add(evidence_request)
    db.commit()
    db.refresh(evidence_request)
    return evidence_request
