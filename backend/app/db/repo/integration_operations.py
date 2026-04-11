"""Repository layer for integration operations."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import IntegrationOperation


def create_integration_operation(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    operation_type: str,
    status: str = "queued",
    incident_id: _uuid.UUID | None = None,
    connection_id: _uuid.UUID | None = None,
    domain: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    payload_json: dict | None = None,
):
    operation = IntegrationOperation(
        org_id=org_id,
        provider=provider,
        operation_type=operation_type,
        status=status,
        incident_id=incident_id,
        connection_id=connection_id,
        domain=domain,
        correlation_id=correlation_id,
        external_reference=external_reference,
        payload_json=payload_json or {},
    )
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation


def list_integration_operations(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(IntegrationOperation)
    if org_id is not None:
        query = query.filter(IntegrationOperation.org_id == org_id)
    if incident_id is not None:
        query = query.filter(IntegrationOperation.incident_id == incident_id)
    if status is not None:
        query = query.filter(IntegrationOperation.status == status)
    if provider is not None:
        query = query.filter(IntegrationOperation.provider == provider)
    if correlation_id is not None:
        query = query.filter(IntegrationOperation.correlation_id == correlation_id)
    if external_reference is not None:
        query = query.filter(
            IntegrationOperation.external_reference == external_reference
        )
    return query.order_by(IntegrationOperation.requested_at_utc.desc()).all()
