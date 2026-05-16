"""Weather map snapshot capture service."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

import httpx
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Artifact, Event, Incident
from app.domain.system_event_types import SystemEventType
from app.services.incident_location_resolver import resolve_incident_location
from app.services.vault_s3 import ArtifactObjectMetadata, VaultS3

WEATHER_MAP_ARTIFACT_TYPE = "weather_map_snapshot"
MAP_DIMENSIONS = "1280x720@2x"
_TWC_TIMESLICE_URL = "https://api.weather.com/v3/TileServer/tile"


class MapOverlayUnavailableError(RuntimeError):
    """Raised when radar overlay cannot be fetched."""


@dataclass(frozen=True)
class RenderedMapSnapshot:
    image_bytes: bytes
    content_type: str
    overlay_applied: bool
    overlay_reason: str | None
    twc_timestamp_iso: str | None


def capture_weather_map_snapshot_if_missing(
    db: Session,
    *,
    incident: Incident,
    request_window_start: datetime | None,
    request_window_end: datetime | None,
    allow_base_only: bool = True,
) -> None:
    incident_id = cast(uuid.UUID, incident.incident_id)
    try:
        _acquire_incident_capture_lock(db, incident_id=incident_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED,
            payload={
                "location": {"lat": None, "lon": None, "source": None, "fallback_reason": "lock_acquire_error"},
                "request_window": {
                    "start": request_window_start.isoformat() if request_window_start else None,
                    "end": request_window_end.isoformat() if request_window_end else None,
                },
                "capture_status": "failed",
                "reason": type(exc).__name__,
            },
        )
        return

    if _snapshot_exists(db, incident_id=incident_id):
        db.rollback()
        return

    try:
        location = resolve_incident_location(
            db,
            incident_id=incident_id,
            window_start=request_window_start,
            window_end=request_window_end,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED,
            payload={
                "location": {"lat": None, "lon": None, "source": None, "fallback_reason": "location_resolution_error"},
                "request_window": {
                    "start": request_window_start.isoformat() if request_window_start else None,
                    "end": request_window_end.isoformat() if request_window_end else None,
                },
                "capture_status": "failed",
                "reason": type(exc).__name__,
            },
        )
        return

    base_payload = _base_payload(location=location, request_window_start=request_window_start, request_window_end=request_window_end)
    _emit_event(
        db,
        incident=incident,
        event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_REQUESTED,
        payload=base_payload,
        commit=False,
    )

    lat, lon = location.get("lat"), location.get("lon")
    if lat is None or lon is None:
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED,
            payload={**base_payload, "capture_status": "failed", "reason": "location_unavailable"},
        )
        return

    try:
        rendered = render_map_snapshot(lat=float(lat), lon=float(lon), allow_base_only=allow_base_only)
    except Exception as exc:  # noqa: BLE001
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED,
            payload={**base_payload, "capture_status": "failed", "reason": type(exc).__name__},
        )
        return

    try:
        artifact = _persist_snapshot_artifact(db, incident=incident, rendered=rendered)
    except Exception as exc:  # noqa: BLE001
        _emit_event(
            db,
            incident=incident,
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED,
            payload={**base_payload, "capture_status": "failed", "reason": type(exc).__name__},
        )
        return
    _emit_event(
        db,
        incident=incident,
        event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_CAPTURED,
        payload={
            **base_payload,
            "capture_status": "ok" if rendered.overlay_applied else "degraded",
            "overlay_applied": rendered.overlay_applied,
            "overlay_unavailable_reason": rendered.overlay_reason,
            "twc_radar_timestamp": rendered.twc_timestamp_iso,
            "artifact_id": str(artifact.artifact_id),
            "artifact_type": WEATHER_MAP_ARTIFACT_TYPE,
        },
    )


def render_map_snapshot(*, lat: float, lon: float, allow_base_only: bool) -> RenderedMapSnapshot:
    base_image_bytes = _fetch_mapbox_base_image(lat=lat, lon=lon)
    base_image = Image.open(io.BytesIO(base_image_bytes)).convert("RGBA")

    try:
        metadata = _fetch_twc_latest_radar_metadata(lat=lat, lon=lon)
        overlay_bytes = _fetch_twc_overlay_png(cast(str, metadata.get("url")))
        overlay = Image.open(io.BytesIO(overlay_bytes)).convert("RGBA")
        composed = Image.alpha_composite(base_image, overlay)
        return _to_rendered_snapshot(composed, overlay_applied=True, overlay_reason=None, twc_timestamp_iso=metadata.get("validTimeUtc"))
    except MapOverlayUnavailableError as exc:
        if not allow_base_only:
            raise
        return _to_rendered_snapshot(base_image, overlay_applied=False, overlay_reason=str(exc), twc_timestamp_iso=None)


def _to_rendered_snapshot(image: Image.Image, *, overlay_applied: bool, overlay_reason: str | None, twc_timestamp_iso: str | None) -> RenderedMapSnapshot:
    output = io.BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=92)
    return RenderedMapSnapshot(
        image_bytes=output.getvalue(),
        content_type="image/jpeg",
        overlay_applied=overlay_applied,
        overlay_reason=overlay_reason,
        twc_timestamp_iso=twc_timestamp_iso,
    )


def _fetch_mapbox_base_image(*, lat: float, lon: float) -> bytes:
    style = "mapbox/satellite-v9"
    token = settings.MAPBOX_TOKEN
    if not style or not token:
        raise RuntimeError("Mapbox configuration missing")
    url = f"https://api.mapbox.com/styles/v1/{style}/static/{lon},{lat},11/{MAP_DIMENSIONS}?access_token={token}"
    response = httpx.get(url, timeout=20.0)
    response.raise_for_status()
    return response.content


def _fetch_twc_latest_radar_metadata(*, lat: float, lon: float) -> dict[str, Any]:
    api_key = settings.TWC_API_KEY
    if not api_key:
        raise MapOverlayUnavailableError("twc_api_key_missing")
    try:
        response = httpx.get(
            _TWC_TIMESLICE_URL,
            params={"product": "radar", "ts": "latest", "lat": lat, "lon": lon, "apiKey": api_key},
            timeout=20.0,
        )
    except httpx.RequestError as exc:
        raise MapOverlayUnavailableError("twc_timeslice_transport_error") from exc
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise MapOverlayUnavailableError(f"twc_timeslice_http_{exc.response.status_code}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise MapOverlayUnavailableError("twc_timeslice_invalid_json") from exc
    timeslices = cast(list[dict[str, Any]], payload.get("seriesInfo", {}).get("radar", {}).get("series") or [])
    if not timeslices:
        raise MapOverlayUnavailableError("twc_timeslice_empty")
    return timeslices[0]


def _fetch_twc_overlay_png(overlay_url: str) -> bytes:
    if not overlay_url:
        raise MapOverlayUnavailableError("twc_overlay_url_missing")
    try:
        response = httpx.get(overlay_url, timeout=20.0)
    except httpx.RequestError as exc:
        raise MapOverlayUnavailableError("twc_overlay_transport_error") from exc
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise MapOverlayUnavailableError(f"twc_overlay_http_{exc.response.status_code}") from exc
    return response.content


def _persist_snapshot_artifact(db: Session, *, incident: Incident, rendered: RenderedMapSnapshot):
    artifact = Artifact(
        incident_id=cast(uuid.UUID, incident.incident_id),
        artifact_type=WEATHER_MAP_ARTIFACT_TYPE,
        status="pending",
        s3_bucket=settings.S3_ARTIFACTS_BUCKET,
    )
    db.add(artifact)
    db.flush()
    key = f"orgs/{incident.org_id}/incidents/{incident.incident_id}/artifacts/{artifact.artifact_id}.jpg"
    metadata = ArtifactObjectMetadata.from_blob(
        data=rendered.image_bytes,
        content_type=rendered.content_type,
        captured_at_utc=datetime.now(timezone.utc),
    )
    try:
        VaultS3(bucket=settings.S3_ARTIFACTS_BUCKET, region=settings.AWS_REGION).put_bytes(
            key, rendered.image_bytes, metadata=metadata
        )
    except Exception:  # noqa: BLE001
        db.delete(artifact)
        db.flush()
        raise
    artifact.status = "captured"
    artifact.s3_key = key
    artifact.sha256 = metadata.sha256
    artifact.byte_size = metadata.byte_size
    db.flush()
    return artifact


def _snapshot_exists(db: Session, *, incident_id: uuid.UUID) -> bool:
    return (
        db.query(Event.id)
        .filter(
            Event.incident_id == incident_id,
            Event.event_type.in_([SystemEventType.WEATHER_MAP_SNAPSHOT_CAPTURED.value, SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED.value]),
        )
        .first()
        is not None
    )


def _acquire_incident_capture_lock(db: Session, *, incident_id: uuid.UUID) -> None:
    db.query(Incident).filter(Incident.incident_id == incident_id).with_for_update().one()


def _base_payload(*, location: dict[str, Any], request_window_start: datetime | None, request_window_end: datetime | None) -> dict[str, Any]:
    return {
        "location": {
            "lat": location.get("lat"),
            "lon": location.get("lon"),
            "source": location.get("source"),
            "fallback_reason": location.get("fallback_reason"),
        },
        "request_window": {
            "start": request_window_start.isoformat() if request_window_start else None,
            "end": request_window_end.isoformat() if request_window_end else None,
        },
    }


def _emit_event(
    db: Session, *, incident: Incident, event_type: SystemEventType, payload: dict, commit: bool = True
) -> None:
    db.add(
        Event(
            org_id=incident.org_id,
            incident_id=cast(uuid.UUID, incident.incident_id),
            event_type=event_type.value,
            actor_type="system",
            actor_id="weather_map_snapshot_service",
            payload=payload,
        )
    )
    if commit:
        db.commit()
