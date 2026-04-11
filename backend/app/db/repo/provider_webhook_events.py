"""Repository layer for provider webhook events."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ProviderWebhookEvent
from app.observability.redaction import redact_payload_for_storage, redact_raw_payload


def create_provider_webhook_event(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    event_type: str,
    status: str = "received",
    incident_id: _uuid.UUID | None = None,
    domain: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    idempotency_key: str | None = None,
    signature_valid: bool | None = None,
    processing_outcome: str | None = None,
    raw_payload: str | None = None,
    payload_json: dict | None = None,
    error_message: str | None = None,
    error_details_json: dict | None = None,
):
    webhook_event = ProviderWebhookEvent(
        org_id=org_id,
        provider=provider,
        event_type=event_type,
        status=status,
        incident_id=incident_id,
        domain=domain,
        correlation_id=correlation_id,
        external_reference=external_reference,
        idempotency_key=idempotency_key,
        signature_valid=signature_valid,
        processing_outcome=processing_outcome,
        raw_payload=redact_raw_payload(raw_payload),
        payload_json=redact_payload_for_storage(payload_json),
        error_message=error_message,
        error_details_json=error_details_json or {},
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    return webhook_event


def update_provider_webhook_event(
    db: Session,
    webhook_event: ProviderWebhookEvent,
    *,
    status: str | None = None,
    signature_valid: bool | None = None,
    processing_outcome: str | None = None,
    error_message: str | None = None,
    error_details_json: dict | None = None,
) -> ProviderWebhookEvent:
    if status is not None:
        webhook_event.status = status
        if status in {"processed", "ignored", "failed"}:
            webhook_event.processed_at_utc = datetime.now(timezone.utc)
    if signature_valid is not None:
        webhook_event.signature_valid = signature_valid
    if processing_outcome is not None:
        webhook_event.processing_outcome = processing_outcome
    if error_message is not None:
        webhook_event.error_message = error_message
    if error_details_json is not None:
        webhook_event.error_details_json = error_details_json
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    return webhook_event


def get_provider_webhook_event_by_idempotency_key(
    db: Session,
    *,
    provider: str,
    event_type: str,
    idempotency_key: str,
) -> ProviderWebhookEvent | None:
    return (
        db.query(ProviderWebhookEvent)
        .filter(
            ProviderWebhookEvent.provider == provider,
            ProviderWebhookEvent.event_type == event_type,
            ProviderWebhookEvent.idempotency_key == idempotency_key,
        )
        .order_by(ProviderWebhookEvent.received_at_utc.desc())
        .first()
    )


def list_provider_webhook_events(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
):
    if org_id is None:
        raise ValueError("org_id is required for provider webhook event queries")
    query = db.query(ProviderWebhookEvent)
    query = query.filter(ProviderWebhookEvent.org_id == org_id)
    if incident_id is not None:
        query = query.filter(ProviderWebhookEvent.incident_id == incident_id)
    if status is not None:
        query = query.filter(ProviderWebhookEvent.status == status)
    if provider is not None:
        query = query.filter(ProviderWebhookEvent.provider == provider)
    if correlation_id is not None:
        query = query.filter(ProviderWebhookEvent.correlation_id == correlation_id)
    if external_reference is not None:
        query = query.filter(ProviderWebhookEvent.external_reference == external_reference)
    return query.order_by(ProviderWebhookEvent.received_at_utc.desc()).all()
