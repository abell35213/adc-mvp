"""Repository layer for provider webhook events."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import ProviderWebhookEvent


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
    payload_json: dict | None = None,
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
        payload_json=payload_json or {},
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    return webhook_event


def list_provider_webhook_events(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(ProviderWebhookEvent)
    if org_id is not None:
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
