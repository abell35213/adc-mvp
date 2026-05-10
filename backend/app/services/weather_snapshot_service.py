"""Capture and persist per-incident weather snapshots with safe failure behavior."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Event, Incident
from app.domain.system_event_types import SystemEventType
from app.services.incident_location_resolver import resolve_incident_location
from app.services.weather.nws_client import build_time_series_url, fetch_nws_time_series_xml
from app.services.weather.nws_parser import parse_nws_time_series_xml


def capture_weather_snapshot_if_missing(
    db: Session,
    *,
    incident: Incident,
    request_window_start: datetime | None,
    request_window_end: datetime | None,
) -> None:
    """Capture weather snapshot once per incident.

    Never raises; failures are recorded as lifecycle events.
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
        requested_payload = {
            "location": {
                "lat": location.get("lat"),
                "lon": location.get("lon"),
                "source": location.get("source"),
                "fallback_reason": location.get("fallback_reason"),
            },
            "request_window": window,
        }
        _emit_event(db, incident=incident, event_type=SystemEventType.WEATHER_SNAPSHOT_REQUESTED, payload=requested_payload)

        lat, lon = location.get("lat"), location.get("lon")
        if lat is None or lon is None or request_window_start is None or request_window_end is None:
            _emit_event(
                db,
                incident=incident,
                event_type=SystemEventType.WEATHER_SNAPSHOT_FAILED,
                payload={**requested_payload, "capture_status": "failed", "reason": "insufficient_request_context"},
            )
            return
        raw_payload = fetch_nws_time_series_xml(lat=float(lat), lon=float(lon), begin=request_window_start, end=request_window_end)
        normalized = parse_nws_time_series_xml(raw_payload)
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_SNAPSHOT_CAPTURED,
            payload={
                **requested_payload,
                "capture_status": "degraded" if normalized.get("is_partial") else "ok",
                "normalized_weather": normalized,
                "raw_source_metadata": {
                    "provider": "nws",
                    "request_url": build_time_series_url(
                        lat=float(lat),
                        lon=float(lon),
                        begin=request_window_start,
                        end=request_window_end,
                    ),
                    "response_length_bytes": len(raw_payload.encode("utf-8")),
                },
            },
        )
    except Exception as exc:  # noqa: BLE001 - caller initiation flow must never fail from weather capture
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_SNAPSHOT_FAILED,
            payload={**requested_payload, "capture_status": "failed", "reason": type(exc).__name__},
        )


def _snapshot_exists(db: Session, *, incident_id: uuid.UUID) -> bool:
    return (
        db.query(Event.id)
        .filter(
            Event.incident_id == incident_id,
            Event.event_type.in_(
                [
                    SystemEventType.WEATHER_SNAPSHOT_CAPTURED.value,
                    SystemEventType.WEATHER_SNAPSHOT_FAILED.value,
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
            actor_id="weather_snapshot_service",
            payload=payload,
        )
    )
    db.commit()
