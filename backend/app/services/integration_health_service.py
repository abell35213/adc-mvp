"""Integration operation/evidence status tracking helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.metrics import MetricNames, increment
from app.db.models import EvidenceRequest, IntegrationOperation
from app.db.repo.integration_operation_status_history import create_operation_status_history


def transition_operation_status(
    db: Session,
    *,
    operation: IntegrationOperation,
    to_status: str,
    message: str | None = None,
    external_reference_id: str | None = None,
):
    """Transition an operation status and write history."""
    from_status = operation.status
    if external_reference_id:
        operation.external_reference_id = external_reference_id
        operation.external_reference = external_reference_id

    if from_status == to_status:
        db.add(operation)
        db.commit()
        db.refresh(operation)
        return operation

    operation.status = to_status
    if to_status == "running" and operation.started_at_utc is None:
        operation.started_at_utc = datetime.now(timezone.utc)
    if to_status in {"succeeded", "failed", "canceled", "downloaded", "unavailable", "partial"}:
        operation.completed_at_utc = datetime.now(timezone.utc)
        if to_status == "unavailable":
            increment(MetricNames.EVIDENCE_UNAVAILABLE_RESULT)
        if to_status == "partial":
            increment(MetricNames.EVIDENCE_PARTIAL_RESULT)
    db.add(operation)
    db.commit()
    db.refresh(operation)

    if (
        operation.started_at_utc is not None
        and operation.completed_at_utc is not None
        and to_status in {"succeeded", "downloaded", "failed", "unavailable"}
    ):
        completion_time_ms = int(
            (operation.completed_at_utc - operation.started_at_utc).total_seconds() * 1000
        )
        increment(MetricNames.EVIDENCE_COMPLETION_TIME, max(completion_time_ms, 0))

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
        external_reference_id=operation.external_reference_id,
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
        if evidence_request.created_at_utc is not None:
            completion_time_ms = int(
                (evidence_request.fulfilled_at_utc - evidence_request.created_at_utc).total_seconds()
                * 1000
            )
            increment(MetricNames.EVIDENCE_COMPLETION_TIME, max(completion_time_ms, 0))
    db.add(evidence_request)
    db.commit()
    db.refresh(evidence_request)
    return evidence_request
