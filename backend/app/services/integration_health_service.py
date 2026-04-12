"""Integration operation/evidence status tracking helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.metrics import MetricNames, increment
from app.db.models import EvidenceRequest, IntegrationConnection, IntegrationOperation
from app.db.repo.integration_operation_status_history import create_operation_status_history


def _safe_duration_ms(start: datetime, end: datetime) -> int:
    """Return non-negative elapsed milliseconds handling naive/aware mismatches."""
    start_dt = start if start.tzinfo is not None else start.replace(tzinfo=timezone.utc)
    end_dt = end if end.tzinfo is not None else end.replace(tzinfo=timezone.utc)
    return max(int((end_dt - start_dt).total_seconds() * 1000), 0)


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
        completion_time_ms = _safe_duration_ms(
            operation.started_at_utc, operation.completed_at_utc
        )
        increment(MetricNames.EVIDENCE_COMPLETION_TIME, completion_time_ms)

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
            completion_time_ms = _safe_duration_ms(
                evidence_request.created_at_utc,
                evidence_request.fulfilled_at_utc,
            )
            increment(MetricNames.EVIDENCE_COMPLETION_TIME, completion_time_ms)
    db.add(evidence_request)
    db.commit()
    db.refresh(evidence_request)
    return evidence_request


def mark_connection_intervention_required(
    db: Session,
    *,
    org_id,
    provider: str,
    domain: str | None,
    reason_code: str,
    admin_action: str,
    message: str,
):
    """Mark matching integration connections as requiring admin intervention."""
    query = db.query(IntegrationConnection).filter(
        IntegrationConnection.org_id == org_id,
        IntegrationConnection.provider == provider,
    )
    if domain is not None:
        query = query.filter(IntegrationConnection.domain == domain)
    connections = query.all()
    for connection in connections:
        config_json = dict(connection.config_json or {})
        config_json["admin_action_required"] = admin_action
        config_json["admin_action_reason_code"] = reason_code
        config_json["admin_action_message"] = message
        connection.config_json = config_json
        connection.status = "error"
        connection.last_synced_at_utc = datetime.now(timezone.utc)
        db.add(connection)
    db.commit()
    return connections
