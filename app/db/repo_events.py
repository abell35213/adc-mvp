"""Repository layer for events."""

from sqlalchemy.orm import Session

from app.db.models import Event


def get_events_by_incident(db: Session, incident_id: int):
    return db.query(Event).filter(Event.incident_id == incident_id).all()


def create_event(db: Session, incident_id: int, event_type: str, payload: str | None = None):
    event = Event(incident_id=incident_id, event_type=event_type, payload=payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
