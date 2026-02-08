"""Repository layer for incidents."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import Incident


def get_incident(db: Session, incident_id: _uuid.UUID):
    return (
        db.query(Incident).filter(Incident.incident_id == incident_id).first()
    )


def list_incidents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Incident).offset(skip).limit(limit).all()


def create_incident(
    db: Session,
    status: str = "open",
    adc_vehicle_id: str | None = None,
    samsara_vehicle_id: str | None = None,
    severity: str | None = None,
):
    incident = Incident(
        status=status,
        adc_vehicle_id=adc_vehicle_id,
        samsara_vehicle_id=samsara_vehicle_id,
        severity=severity,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident
