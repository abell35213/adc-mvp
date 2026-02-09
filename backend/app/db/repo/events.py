"""Repository layer for events (append-only)."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import Event


def get_events_by_incident(db: Session, incident_id: _uuid.UUID):
    return db.query(Event).filter(Event.incident_id == incident_id).all()


def create_event(
    db: Session,
    incident_id: _uuid.UUID,
    event_type: str,
    actor_type: str,
    actor_id: str,
    payload: dict | None = None,
):
    """Append a new event. Events are never updated or deleted."""
    event = Event(
        incident_id=incident_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
