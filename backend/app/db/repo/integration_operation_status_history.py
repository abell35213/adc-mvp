"""Repository layer for integration operation status history."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import IntegrationOperationStatusHistory


def create_operation_status_history(
    db: Session,
    operation_id: _uuid.UUID,
    provider: str,
    to_status: str,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    domain: str | None = None,
    from_status: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    external_reference_id: str | None = None,
    message: str | None = None,
):
    history = IntegrationOperationStatusHistory(
        operation_id=operation_id,
        provider=provider,
        to_status=to_status,
        org_id=org_id,
        incident_id=incident_id,
        domain=domain,
        from_status=from_status,
        correlation_id=correlation_id,
        external_reference=external_reference,
        external_reference_id=external_reference_id or external_reference,
        message=message,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def list_operation_status_history(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    external_reference_id: str | None = None,
):
    query = db.query(IntegrationOperationStatusHistory)
    if org_id is not None:
        query = query.filter(IntegrationOperationStatusHistory.org_id == org_id)
    if incident_id is not None:
        query = query.filter(IntegrationOperationStatusHistory.incident_id == incident_id)
    if status is not None:
        query = query.filter(IntegrationOperationStatusHistory.to_status == status)
    if provider is not None:
        query = query.filter(IntegrationOperationStatusHistory.provider == provider)
    if correlation_id is not None:
        query = query.filter(
            IntegrationOperationStatusHistory.correlation_id == correlation_id
        )
    if external_reference is not None:
        query = query.filter(
            IntegrationOperationStatusHistory.external_reference == external_reference
        )
    if external_reference_id is not None:
        query = query.filter(
            IntegrationOperationStatusHistory.external_reference_id == external_reference_id
        )
    return query.order_by(IntegrationOperationStatusHistory.created_at_utc.desc()).all()
