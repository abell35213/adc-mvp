"""Capture weather map snapshot lifecycle markers with idempotent behavior."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Event, Incident
from app.domain.system_event_types import SystemEventType
from app.services.incident_location_resolver import resolve_incident_location


def capture_weather_map_snapshot_if_missing(
    db: Session,
    *,
    incident: Incident,
    request_window_start: datetime | None,
    request_window_end: datetime | None,
) -> None:
    """Capture weather map snapshot once per incident.

    Current implementation records request + capture/failure lifecycle events
    and remains non-blocking for incident workflows.
    """
    if _snapshot_exists(db, incident_id=incident.incident_id):
        return

    try:
        location = resolve_incident_location(
            db,
            incident_id=incident.incident_id,
            window_start=request_window_start,
            window_end=request_window_end,
        )
        window = {
            "start": request_window_start.isoformat() if request_window_start else None,
            "end": request_window_end.isoformat() if request_window_end else None,
        }
        base_payload = {
            "location": {
                "lat": location.get("lat"),
                "lon": location.get("lon"),
                "source": location.get("source"),
                "fallback_reason": location.get("fallback_reason"),
            },
            "request_window": window,
        }
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_REQUESTED,
            payload=base_payload,
        )
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_CAPTURED,
            payload={**base_payload, "capture_status": "ok"},
        )
    except Exception as exc:  # noqa: BLE001
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED,
            payload={"capture_status": "failed", "reason": type(exc).__name__},
        )


def _snapshot_exists(db: Session, *, incident_id: uuid.UUID) -> bool:
    return (
        db.query(Event.id)
        .filter(
            Event.incident_id == incident_id,
            Event.event_type.in_(
                [
                    SystemEventType.WEATHER_MAP_SNAPSHOT_CAPTURED.value,
                    SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED.value,
                ]
            ),
        )
        .first()
        is not None
    )


def _emit_event(db: Session, *, incident: Incident, event_type: SystemEventType, payload: dict) -> None:
    db.add(
        Event(
            org_id=incident.org_id,
            incident_id=incident.incident_id,
            event_type=event_type.value,
            actor_type="system",
            actor_id="weather_map_snapshot_service",
            payload=payload,
        )
    )
    db.commit()
