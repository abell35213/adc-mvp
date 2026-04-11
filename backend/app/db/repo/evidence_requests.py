"""Repository layer for evidence requests."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import EvidenceRequest
from app.integrations.errors import NormalizedIntegrationError


def create_evidence_request(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    status: str = "open",
    incident_id: _uuid.UUID | None = None,
    operation_id: _uuid.UUID | None = None,
    domain: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    request_payload_json: dict | None = None,
    normalized_error: NormalizedIntegrationError | None = None,
):
    normalized_payload = normalized_error.to_dict() if normalized_error else None
    evidence_request = EvidenceRequest(
        org_id=org_id,
        provider=provider,
        status=status,
        incident_id=incident_id,
        operation_id=operation_id,
        domain=domain,
        correlation_id=correlation_id,
        external_reference=external_reference,
        request_payload_json=request_payload_json or {},
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
    )
    db.add(evidence_request)
    db.commit()
    db.refresh(evidence_request)
    return evidence_request


def update_evidence_request_error(
    db: Session,
    evidence_request: EvidenceRequest,
    normalized_error: NormalizedIntegrationError,
) -> EvidenceRequest:
    payload = normalized_error.to_dict()
    evidence_request.error_code = str(payload["code"])
    evidence_request.error_category = str(payload["category"])
    evidence_request.error_provider_key = str(payload["provider_key"])
    evidence_request.error_retryable = bool(payload["retryable"])
    evidence_request.error_user_facing_message = str(payload["user_facing_message"])
    evidence_request.error_operator_message = str(payload["operator_message"])
    db.add(evidence_request)
    db.commit()
    db.refresh(evidence_request)
    return evidence_request


def list_evidence_requests(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(EvidenceRequest)
    if org_id is not None:
        query = query.filter(EvidenceRequest.org_id == org_id)
    if incident_id is not None:
        query = query.filter(EvidenceRequest.incident_id == incident_id)
    if status is not None:
        query = query.filter(EvidenceRequest.status == status)
    if provider is not None:
        query = query.filter(EvidenceRequest.provider == provider)
    if correlation_id is not None:
        query = query.filter(EvidenceRequest.correlation_id == correlation_id)
    if external_reference is not None:
        query = query.filter(EvidenceRequest.external_reference == external_reference)
    return query.order_by(EvidenceRequest.requested_at_utc.desc()).all()
