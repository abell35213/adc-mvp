"""Service logic for driver incident report write operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Driver, Event, Incident
from app.domain.system_event_types import SystemEventType

REPORT_SECTIONS = ("scene", "parties", "narrative")
SECTION_EVENT_TYPES = {
    "scene": SystemEventType.DRIVER_SCENE_FACTS_SAVED.value,
    "parties": SystemEventType.DRIVER_PARTIES_SAVED.value,
    "narrative": SystemEventType.DRIVER_NARRATIVE_SAVED.value,
}


def _validate_incident_write_scope(
    db: Session,
    incident_id: uuid.UUID,
    driver: Driver,
) -> Incident:
    incident = (
        db.query(Incident)
        .filter(
            Incident.incident_id == incident_id,
            Incident.org_id == driver.org_id,
            Incident.adc_driver_id == str(driver.driver_id),
        )
        .first()
    )
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found"
        )

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
                event_type=SECTION_EVENT_TYPES[section],
                actor_type="driver_app",
                actor_id=str(driver.driver_id),
                payload=payload,
            )
        )
        updated_sections.append(section)

    if not updated_sections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    submitted_at_utc = datetime.now(timezone.utc)

    db.add(
        Event(
            org_id=incident.org_id,
            incident_id=incident.incident_id,
            event_type=SystemEventType.DRIVER_REPORT_SUBMITTED.value,
            actor_type="driver_app",
            actor_id=str(driver.driver_id),
            occurred_at_utc=submitted_at_utc,
            payload={
                "driver_report_submitted": True,
                "submitted": True,
                "submitted_at_utc": submitted_at_utc.isoformat(),
            },
        )
    )
    db.commit()
