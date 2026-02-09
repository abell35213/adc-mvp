"""Repository layer for incidents."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import Incident


def get_incident(
    db: Session,
    incident_id: _uuid.UUID,
    org_ids: list[_uuid.UUID] | None = None,
):
    query = db.query(Incident).filter(Incident.incident_id == incident_id)
    if org_ids is not None:
        query = query.filter(Incident.org_id.in_(org_ids))
    return query.first()


def list_incidents(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    org_ids: list[_uuid.UUID] | None = None,
):
    query = db.query(Incident)
    if org_ids is not None:
        query = query.filter(Incident.org_id.in_(org_ids))
    return query.offset(skip).limit(limit).all()


def create_incident(
    db: Session,
    status: str = "open",
    adc_vehicle_id: str | None = None,
    samsara_vehicle_id: str | None = None,
    adc_driver_id: str | None = None,
    severity: str | None = None,
    org_id: _uuid.UUID | None = None,
):
    incident = Incident(
        status=status,
        adc_vehicle_id=adc_vehicle_id,
        samsara_vehicle_id=samsara_vehicle_id,
        adc_driver_id=adc_driver_id,
        severity=severity,
        org_id=org_id,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident
