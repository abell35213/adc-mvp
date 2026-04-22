"""Database queries for immutable audit events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.audit.models import AuditEventCreate, AuditEventRetentionUpdate
from app.db.models import AuditEvent


class AuditEventQueryFilters(dict):
    """Typed mapping helper for querying audit event timelines."""


def insert_audit_event(db: Session, payload: AuditEventCreate) -> AuditEvent:
    """Insert a new append-only audit event."""
    audit_event = AuditEvent(
        org_id=payload.org_id,
        incident_id=payload.incident_id,
        export_id=payload.export_id,
        artifact_id=payload.artifact_id,
        actor_type=payload.actor_type,
        actor_id=payload.actor_id,
        action=payload.action,
        event_type=payload.event_type,
        outcome=payload.outcome,
        metadata_json=payload.metadata,
        occurred_at_utc=payload.occurred_at_utc,
    )
    db.add(audit_event)
    db.commit()
    db.refresh(audit_event)
    return audit_event


def list_audit_events(
    db: Session,
    *,
    org_id: uuid.UUID,
    incident_id: uuid.UUID | None = None,
    export_id: uuid.UUID | None = None,
    actor_id: str | None = None,
    event_type: str | None = None,
    occurred_after_utc: datetime | None = None,
    occurred_before_utc: datetime | None = None,
    limit: int = 500,
) -> list[AuditEvent]:
    """List audit events by common indexed filters."""
    query = db.query(AuditEvent).filter(AuditEvent.org_id == org_id)

    if incident_id is not None:
        query = query.filter(AuditEvent.incident_id == incident_id)
    if export_id is not None:
        query = query.filter(AuditEvent.export_id == export_id)
    if actor_id is not None:
        query = query.filter(AuditEvent.actor_id == actor_id)
    if event_type is not None:
        query = query.filter(AuditEvent.event_type == event_type)
    if occurred_after_utc is not None:
        query = query.filter(AuditEvent.occurred_at_utc >= occurred_after_utc)
    if occurred_before_utc is not None:
        query = query.filter(AuditEvent.occurred_at_utc <= occurred_before_utc)

    return query.order_by(AuditEvent.occurred_at_utc.desc()).limit(limit).all()


def list_audit_events_for_admin(
    db: Session,
    *,
    org_id: uuid.UUID | None = None,
    actor_id: str | None = None,
    event_type: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    occurred_after_utc: datetime | None = None,
    occurred_before_utc: datetime | None = None,
    limit: int = 500,
) -> list[AuditEvent]:
    """List audit events for privileged users across orgs (optionally scoped)."""
    query = db.query(AuditEvent)
    if org_id is not None:
        query = query.filter(AuditEvent.org_id == org_id)
    if actor_id is not None:
        query = query.filter(AuditEvent.actor_id == actor_id)
    if event_type is not None:
        query = query.filter(AuditEvent.event_type == event_type)
    if action is not None:
        query = query.filter(AuditEvent.action == action)
    if outcome is not None:
        query = query.filter(AuditEvent.outcome == outcome)
    if occurred_after_utc is not None:
        query = query.filter(AuditEvent.occurred_at_utc >= occurred_after_utc)
    if occurred_before_utc is not None:
        query = query.filter(AuditEvent.occurred_at_utc <= occurred_before_utc)
    return query.order_by(AuditEvent.occurred_at_utc.desc()).limit(limit).all()


def update_audit_event_retention(
    db: Session,
    *,
    audit_event_id: uuid.UUID,
    retention: AuditEventRetentionUpdate,
) -> AuditEvent | None:
    """Update retention-only fields for an audit event."""
    audit_event = db.query(AuditEvent).filter(AuditEvent.id == audit_event_id).first()
    if audit_event is None:
        return None

    audit_event.retention_expires_at_utc = retention.retention_expires_at_utc
    audit_event.retention_purged_at_utc = retention.retention_purged_at_utc
    db.commit()
    db.refresh(audit_event)
    return audit_event
