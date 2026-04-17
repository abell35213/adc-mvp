"""Service interface for audit event storage and retrieval."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.audit.models import AuditEventCreate, AuditEventRetentionUpdate
from app.audit.queries import (
    insert_audit_event,
    list_audit_events,
    list_audit_events_for_admin,
    update_audit_event_retention,
)
from app.db.models import AuditEvent


def append_event(db: Session, payload: AuditEventCreate) -> AuditEvent:
    """Append a new immutable audit event row."""
    return insert_audit_event(db, payload)


def get_events(
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
    """Read audit events using indexed dimensions and timestamp range filters."""
    return list_audit_events(
        db,
        org_id=org_id,
        incident_id=incident_id,
        export_id=export_id,
        actor_id=actor_id,
        event_type=event_type,
        occurred_after_utc=occurred_after_utc,
        occurred_before_utc=occurred_before_utc,
        limit=limit,
    )


def set_retention(
    db: Session,
    *,
    audit_event_id: uuid.UUID,
    retention_expires_at_utc: datetime | None = None,
    retention_purged_at_utc: datetime | None = None,
) -> AuditEvent | None:
    """Set retention-only mutable fields for an existing audit event."""
    return update_audit_event_retention(
        db,
        audit_event_id=audit_event_id,
        retention=AuditEventRetentionUpdate(
            retention_expires_at_utc=retention_expires_at_utc,
            retention_purged_at_utc=retention_purged_at_utc,
        ),
    )


def get_events_for_admin(
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
    """Read audit events across org scope for privileged/internal users."""
    return list_audit_events_for_admin(
        db,
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        action=action,
        outcome=outcome,
        occurred_after_utc=occurred_after_utc,
        occurred_before_utc=occurred_before_utc,
        limit=limit,
    )
