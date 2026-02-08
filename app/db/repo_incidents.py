"""Repository layer for incidents."""

from sqlalchemy.orm import Session

from app.db.models import Incident


def get_incident(db: Session, incident_id: int):
    return db.query(Incident).filter(Incident.id == incident_id).first()


def list_incidents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Incident).offset(skip).limit(limit).all()


def create_incident(db: Session, title: str, description: str | None = None):
    incident = Incident(title=title, description=description)
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident
