"""Repository layer for integration operations."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import IntegrationOperation
from app.integrations.errors import NormalizedIntegrationError


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
    external_reference_id: str | None = None,
    payload_json: dict | None = None,
    normalized_error: NormalizedIntegrationError | None = None,
):
    normalized_payload = normalized_error.to_dict() if normalized_error else None
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
        external_reference_id=external_reference_id or external_reference,
        payload_json=payload_json or {},
        error_code=normalized_payload["code"] if normalized_payload else None,
        error_category=normalized_payload["category"] if normalized_payload else None,
        error_provider_key=(
            normalized_payload["provider_key"] if normalized_payload else None
        ),
        error_retryable=normalized_payload["retryable"] if normalized_payload else None,
        error_user_facing_message=(
            normalized_payload["user_facing_message"] if normalized_payload else None
        ),
        error_operator_message=(
            normalized_payload["operator_message"] if normalized_payload else None
        ),
        error_message=normalized_payload["operator_message"] if normalized_payload else None,
    )
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation


def update_integration_operation_error(
    db: Session,
    operation: IntegrationOperation,
    normalized_error: NormalizedIntegrationError,
) -> IntegrationOperation:
    payload = normalized_error.to_dict()
    operation.error_code = str(payload["code"])
    operation.error_category = str(payload["category"])
    operation.error_provider_key = str(payload["provider_key"])
    operation.error_retryable = bool(payload["retryable"])
    operation.error_user_facing_message = str(payload["user_facing_message"])
    operation.error_operator_message = str(payload["operator_message"])
    operation.error_message = str(payload["operator_message"])
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
    external_reference_id: str | None = None,
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
    if external_reference_id is not None:
        query = query.filter(
            IntegrationOperation.external_reference_id == external_reference_id
        )
    return query.order_by(IntegrationOperation.requested_at_utc.desc()).all()
