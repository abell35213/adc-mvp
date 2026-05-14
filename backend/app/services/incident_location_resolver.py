"""Resolve an incident location with graceful fallback ordering."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import Event, Incident
from app.domain.system_event_types import SystemEventType
from app.integrations.service import get_telematics_provider


@dataclass(frozen=True)
class IncidentLocationResolution:
    lat: float | None
    lon: float | None
    source: str
    fallback_reason: str | None


_DEVICE_LOCATION_SOURCE = "device_location"
_ELD_CURRENT_SOURCE = "eld_current"
_ELD_LAST_KNOWN_SOURCE = "eld_last_known"
_UNAVAILABLE_SOURCE = "unavailable"


def resolve_incident_location(
    db: Session,
    *,
    incident_id: uuid.UUID,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, Any]:
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if incident is None:
        return _unavailable("incident_not_found")

    device_location = _resolve_device_location(db, incident_id=incident_id)
    if device_location is not None:
        return device_location

    telematics = _resolve_telematics_location(incident, window_start=window_start, window_end=window_end)
    if telematics is not None:
        return telematics

    return _unavailable("no_location_available")


def _resolve_device_location(db: Session, *, incident_id: uuid.UUID) -> dict[str, Any] | None:
    event = (
        db.query(Event)
        .filter(
            Event.incident_id == incident_id,
            Event.event_type == SystemEventType.INCIDENT_PROTOCOL_INITIATED.value,
        )
        .order_by(desc(Event.occurred_at_utc), desc(Event.created_at_utc))
        .first()
    )
    if event is None:
        return None

    payload: dict[str, Any] = dict(cast(Any, event.payload) or {})
    maybe_device_location = payload.get("device_location") if isinstance(payload, dict) else None
    coords = _extract_lat_lon(maybe_device_location)
    if coords is None:
        return None
    return _resolved(*coords, source=_DEVICE_LOCATION_SOURCE)


def _resolve_telematics_location(
    incident: Incident, *, window_start: datetime | None, window_end: datetime | None
) -> dict[str, Any] | None:
    provider = get_telematics_provider()
    start = window_start.isoformat() if window_start else None
    end = window_end.isoformat() if window_end else None
    current = _extract_from_rows(provider.fetch_gps_window(start=start, end=end), incident=incident)
    if current is not None:
        return _resolved(*current, source=_ELD_CURRENT_SOURCE)

    last_known = _extract_from_rows(provider.fetch_vehicle_state(start=start, end=end), incident=incident)
    if last_known is not None:
        return _resolved(*last_known, source=_ELD_LAST_KNOWN_SOURCE)

    return None


def _extract_from_rows(rows: list[dict[str, Any]], *, incident: Incident) -> tuple[float, float] | None:
    for row in rows:
        if not _row_matches_incident(row, incident=incident):
            continue
        coords = _extract_lat_lon(row)
        if coords is not None:
            return coords
    return None


def _row_matches_incident(row: dict[str, Any], *, incident: Incident) -> bool:
    if incident.samsara_vehicle_id is None and incident.adc_vehicle_id is None:
        return False

    if incident.samsara_vehicle_id and str(row.get("vehicleId")) == str(incident.samsara_vehicle_id):
        return True
    if incident.adc_vehicle_id and str(row.get("vehicleId")) == str(incident.adc_vehicle_id):
        return True
    return False


def _extract_lat_lon(payload: Any) -> tuple[float, float] | None:
    if not isinstance(payload, dict):
        return None

    lat = payload.get("lat")
    lon = payload.get("lon")
    if lat is None or lon is None:
        lat = payload.get("latitude")
        lon = payload.get("longitude")
    if lat is None or lon is None:
        return None

    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _resolved(lat: float, lon: float, *, source: str) -> dict[str, Any]:
    return {"lat": lat, "lon": lon, "source": source, "fallback_reason": None}


def _unavailable(reason: str) -> dict[str, Any]:
    return {"lat": None, "lon": None, "source": _UNAVAILABLE_SOURCE, "fallback_reason": reason}
