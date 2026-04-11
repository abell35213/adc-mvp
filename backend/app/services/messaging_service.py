"""Helpers for writing incident timeline/system events."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.repo.events import create_event


def emit_timeline_event(
    db: Session,
    *,
    incident_id: uuid.UUID,
    event_type: str,
    actor_type: str,
    actor_id: str,
    payload: dict | None = None,
):
    """Append a timeline event for an incident."""
    return create_event(
        db,
        incident_id=incident_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
    )
