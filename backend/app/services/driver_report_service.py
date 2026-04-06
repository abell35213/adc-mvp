"""Service logic for driver incident report write operations."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Driver, Event, Incident
from app.domain.system_event_types import SystemEventType

REPORT_SECTIONS = ("scene", "parties", "narrative")


def _validate_incident_write_scope(
    db: Session,
    incident_id: uuid.UUID,
    driver: Driver,
) -> Incident:
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found"
        )

    if incident.org_id != driver.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if incident.adc_driver_id is not None and incident.adc_driver_id != str(
        driver.driver_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return incident


def patch_report_sections(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
    patch: dict,
) -> list[str]:
    incident = _validate_incident_write_scope(db, incident_id, driver)
    updated_sections: list[str] = []

    for section in REPORT_SECTIONS:
        if section not in patch:
            continue

        value = patch[section]
        payload = {
            "report_section": section,
            "report_value": value,
            "submitted": False,
        }
        db.add(
            Event(
                org_id=incident.org_id,
                incident_id=incident.incident_id,
                event_type=SystemEventType.INCIDENT_UPDATED.value,
                actor_type="driver_app",
                actor_id=str(driver.driver_id),
                payload=payload,
            )
        )
        updated_sections.append(section)

    if not updated_sections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one report section must be provided",
        )

    db.commit()
    return updated_sections


def submit_driver_report(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
) -> None:
    incident = _validate_incident_write_scope(db, incident_id, driver)

    db.add(
        Event(
            org_id=incident.org_id,
            incident_id=incident.incident_id,
            event_type=SystemEventType.INCIDENT_UPDATED.value,
            actor_type="driver_app",
            actor_id=str(driver.driver_id),
            payload={
                "driver_report_submitted": True,
                "submitted": True,
            },
        )
    )
    db.commit()
