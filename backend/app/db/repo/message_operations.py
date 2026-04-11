"""Repository layer for message operations."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import MessageOperation


def create_message_operation(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    status: str = "queued",
    incident_id: _uuid.UUID | None = None,
    operation_id: _uuid.UUID | None = None,
    domain: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    payload_json: dict | None = None,
):
    message_operation = MessageOperation(
        org_id=org_id,
        provider=provider,
        status=status,
        incident_id=incident_id,
        operation_id=operation_id,
        domain=domain,
        correlation_id=correlation_id,
        external_reference=external_reference,
        payload_json=payload_json or {},
    )
    db.add(message_operation)
    db.commit()
    db.refresh(message_operation)
    return message_operation


def list_message_operations(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(MessageOperation)
    if org_id is not None:
        query = query.filter(MessageOperation.org_id == org_id)
    if incident_id is not None:
        query = query.filter(MessageOperation.incident_id == incident_id)
    if status is not None:
        query = query.filter(MessageOperation.status == status)
    if provider is not None:
        query = query.filter(MessageOperation.provider == provider)
    if correlation_id is not None:
        query = query.filter(MessageOperation.correlation_id == correlation_id)
    if external_reference is not None:
        query = query.filter(MessageOperation.external_reference == external_reference)
    return query.order_by(MessageOperation.created_at_utc.desc()).all()
