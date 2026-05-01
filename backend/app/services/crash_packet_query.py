"""Canonical crash-packet query.

This module owns *the single query* the crash-packet workflow runs the moment
an incident's status flips to ``accident_occurred``. Per the v2 plan:

> The reason for one SQL is exactly what you asked: deterministic, easy to
> reason about, easy to add columns to, and easy to mock in tests with a
> single fixture row.

The function returns a ``CrashPacketRow`` dataclass whose attributes line up
with the columns the JSONB-aggregating production query would emit. It is
expressed via the SQLAlchemy ORM so the same code runs against PostgreSQL in
production and SQLite in tests.

Phase-1 sections (Phase 2 will add trailer + TMS-cached maintenance):

* ``incident_json`` — incident core
* ``driver_json`` — driver bio (when an Org-side driver record exists)
* ``driver_history_json`` — all prior incidents for ``adc_driver_id``
* ``vehicle_json`` — tractor/vehicle row (from ``OrgVehicleRegistry``)
* ``maintenance_json`` — last 1 year of maintenance records (Phase 2 wires
  this to TMS-cached data; today returns ``[]``)
* ``eld_logs_json`` — last 8-day artifact references (HOS/ELD)
* ``samsara_clip_links_json`` — Samsara deep links for dashcam clips
* ``related_event_count`` — count of timeline events for the incident
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    Artifact,
    Driver,
    Event,
    Incident,
    MaintenanceRecord,
    OrgVehicleRegistry,
    Trailer,
)

# 1-year maintenance lookback per the user's clarifying note (#5):
# "The maintenance history should be the past year. not 90 days."
MAINTENANCE_LOOKBACK_DAYS = 365

# Samsara deep-link template; the cloud route accepts a vehicleId/clip path.
# Falls back to a Samsara-domain URL even when only the vehicle id is known.
SAMSARA_DEEP_LINK_BASE = "https://cloud.samsara.com"


@dataclass
class CrashPacketRow:
    """Aggregated payload for the crash-packet builder.

    Mirrors what a single ``SELECT … json_build_object(...) …`` would return
    on PostgreSQL, but assembled via the ORM so the canonical SQL is
    portable across dialects (and trivial to mock in tests).
    """

    incident_json: dict[str, Any]
    driver_json: dict[str, Any] | None
    driver_history_json: list[dict[str, Any]] = field(default_factory=list)
    vehicle_json: dict[str, Any] | None = None
    trailer_json: dict[str, Any] | None = None  # populated in Phase 2
    maintenance_json: list[dict[str, Any]] = field(default_factory=list)  # Phase 2
    eld_logs_json: list[dict[str, Any]] = field(default_factory=list)
    samsara_clip_links_json: list[dict[str, Any]] = field(default_factory=list)
    related_event_count: int = 0

    @property
    def maintenance_window_days(self) -> int:
        return MAINTENANCE_LOOKBACK_DAYS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_incident(incident: Incident) -> dict[str, Any]:
    return {
        "incident_id": str(incident.incident_id),
        "org_id": str(incident.org_id) if incident.org_id else None,
        "status": incident.status,
        "case_status": incident.case_status,
        "severity": incident.severity,
        "adc_vehicle_id": incident.adc_vehicle_id,
        "samsara_vehicle_id": incident.samsara_vehicle_id,
        "adc_driver_id": incident.adc_driver_id,
        "adc_trailer_id": incident.adc_trailer_id,
        "created_at_utc": (
            incident.created_at_utc.isoformat() if incident.created_at_utc else None
        ),
        "updated_at_utc": (
            incident.updated_at_utc.isoformat() if incident.updated_at_utc else None
        ),
    }


def _serialize_driver(driver: Driver) -> dict[str, Any]:
    return {
        "driver_id": str(driver.driver_id),
        "display_name": driver.display_name,
        "phone_e164": driver.phone_e164,
        "is_active": bool(driver.is_active),
    }


def _serialize_vehicle(vehicle: OrgVehicleRegistry) -> dict[str, Any]:
    return {
        "vehicle_id": str(vehicle.vehicle_id),
        "unit_number": vehicle.unit_number,
        "vin": vehicle.vin,
        "provider": vehicle.provider,
        "provider_vehicle_id": vehicle.provider_vehicle_id,
        "is_active": bool(vehicle.is_active),
    }


def _serialize_trailer(trailer: Trailer) -> dict[str, Any]:
    return {
        "trailer_id": str(trailer.id),
        "adc_trailer_id": trailer.adc_trailer_id,
        "vin": trailer.vin,
        "make": trailer.make,
        "model": trailer.model,
        "year": trailer.year,
        "plate": trailer.plate,
        "last_inspection_at_utc": (
            trailer.last_inspection_at_utc.isoformat()
            if trailer.last_inspection_at_utc
            else None
        ),
        "source": trailer.source,
        "external_id": trailer.external_id,
    }


def _serialize_maintenance(record: MaintenanceRecord) -> dict[str, Any]:
    return {
        "maintenance_record_id": str(record.id),
        "asset_kind": record.asset_kind,
        "asset_id": record.asset_id,
        "performed_at_utc": (
            record.performed_at_utc.isoformat()
            if record.performed_at_utc
            else None
        ),
        "vendor": record.vendor,
        "summary": record.summary,
        "mileage": record.mileage,
        "source": record.source,
        "external_id": record.external_id,
    }


def _serialize_artifact(artifact: Artifact) -> dict[str, Any]:
    return {
        "artifact_id": str(artifact.artifact_id),
        "artifact_type": artifact.artifact_type,
        "status": artifact.status,
        "capture_window_start_utc": (
            artifact.capture_window_start_utc.isoformat()
            if artifact.capture_window_start_utc
            else None
        ),
        "capture_window_end_utc": (
            artifact.capture_window_end_utc.isoformat()
            if artifact.capture_window_end_utc
            else None
        ),
        "s3_bucket": artifact.s3_bucket,
        "s3_key": artifact.s3_key,
        "byte_size": artifact.byte_size,
    }


def _build_samsara_clip_link(
    *, samsara_vehicle_id: str | None, artifact: Artifact
) -> dict[str, Any]:
    """Compose the Samsara deep link for a dashcam clip.

    Per clarifying answer #6 we link back to the clip in Samsara rather than
    embedding bytes. When ``samsara_vehicle_id`` is missing, we still surface
    the artifact reference so the safety manager has *something* to follow.
    """
    deep_link: str | None = None
    if samsara_vehicle_id:
        # Time-window deep link into the Samsara cloud video player. The
        # window comes from the artifact's capture window so reviewers land
        # on the relevant footage.
        start = artifact.capture_window_start_utc
        end = artifact.capture_window_end_utc
        if start and end:
            deep_link = (
                f"{SAMSARA_DEEP_LINK_BASE}/o/fleet/vehicles/{samsara_vehicle_id}"
                f"/dashcam?startTime={int(start.timestamp() * 1000)}"
                f"&endTime={int(end.timestamp() * 1000)}"
            )
        else:
            deep_link = (
                f"{SAMSARA_DEEP_LINK_BASE}/o/fleet/vehicles/{samsara_vehicle_id}/dashcam"
            )
    return {
        "artifact_id": str(artifact.artifact_id),
        "artifact_type": artifact.artifact_type,
        "samsara_vehicle_id": samsara_vehicle_id,
        "deep_link": deep_link,
        "fallback_s3_bucket": artifact.s3_bucket,
        "fallback_s3_key": artifact.s3_key,
    }


def fetch_crash_packet_row(
    db: Session, *, incident_id: _uuid.UUID
) -> CrashPacketRow:
    """Run the canonical crash-packet query for ``incident_id``.

    Returns a populated :class:`CrashPacketRow`. Raises ``LookupError`` when
    the incident does not exist (the dispatch task converts this to a
    terminal failure rather than a retry).
    """
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if incident is None:
        raise LookupError(f"Incident {incident_id} not found")

    org_id = incident.org_id
    adc_driver_id = incident.adc_driver_id
    adc_vehicle_id = incident.adc_vehicle_id

    # Driver — only present when an Org-side driver record exists. The
    # ``adc_driver_id`` on Incident is opaque text (often the driver UUID),
    # so we look it up best-effort.
    driver_obj = None
    if adc_driver_id and org_id:
        try:
            driver_uuid = _uuid.UUID(adc_driver_id)
        except (ValueError, AttributeError):
            driver_uuid = None
        if driver_uuid is not None:
            driver_obj = (
                db.query(Driver)
                .filter(Driver.org_id == org_id, Driver.driver_id == driver_uuid)
                .first()
            )

    # Driver history — all prior incidents for the same adc_driver_id,
    # regardless of status, excluding the one we're reporting on.
    driver_history: list[dict[str, Any]] = []
    if adc_driver_id and org_id:
        prior = (
            db.query(Incident)
            .filter(
                Incident.org_id == org_id,
                Incident.adc_driver_id == adc_driver_id,
                Incident.incident_id != incident_id,
            )
            .order_by(Incident.created_at_utc.desc())
            .limit(50)
            .all()
        )
        driver_history = [
            {
                "incident_id": str(p.incident_id),
                "created_at_utc": p.created_at_utc.isoformat()
                if p.created_at_utc
                else None,
                "status": p.status,
                "severity": p.severity,
            }
            for p in prior
        ]

    # Vehicle / tractor.
    vehicle_obj = None
    if adc_vehicle_id and org_id:
        vehicle_obj = (
            db.query(OrgVehicleRegistry)
            .filter(
                OrgVehicleRegistry.org_id == org_id,
                OrgVehicleRegistry.unit_number == adc_vehicle_id,
            )
            .first()
        )

    # Trailer (Phase 2): joined via incident.adc_trailer_id.
    adc_trailer_id = incident.adc_trailer_id
    trailer_obj: Trailer | None = None
    if adc_trailer_id and org_id:
        trailer_obj = (
            db.query(Trailer)
            .filter(
                Trailer.org_id == org_id,
                Trailer.adc_trailer_id == adc_trailer_id,
            )
            .first()
        )

    # Maintenance (Phase 2): combined tractor + trailer, last 1 year.
    maintenance: list[dict[str, Any]] = []
    if org_id:
        cutoff = _utcnow() - timedelta(days=MAINTENANCE_LOOKBACK_DAYS)
        maint_filters = []
        if adc_vehicle_id:
            maint_filters.append(
                (MaintenanceRecord.asset_kind == "tractor")
                & (MaintenanceRecord.asset_id == adc_vehicle_id)
            )
        if adc_trailer_id:
            maint_filters.append(
                (MaintenanceRecord.asset_kind == "trailer")
                & (MaintenanceRecord.asset_id == adc_trailer_id)
            )
        if maint_filters:
            from sqlalchemy import or_

            records = (
                db.query(MaintenanceRecord)
                .filter(
                    MaintenanceRecord.org_id == org_id,
                    MaintenanceRecord.performed_at_utc >= cutoff,
                    or_(*maint_filters),
                )
                .order_by(MaintenanceRecord.performed_at_utc.desc())
                .all()
            )
            maintenance = [_serialize_maintenance(r) for r in records]

    # ELD artifacts (any HOS/ELD-bearing artifact captured for this incident).
    eld_artifacts = (
        db.query(Artifact)
        .filter(
            Artifact.incident_id == incident_id,
            Artifact.artifact_type.in_(
                ("eld_log_report", "eld_log", "telematics_eld")
            ),
        )
        .order_by(Artifact.created_at_utc.desc())
        .limit(8)
        .all()
    )
    eld_logs = [_serialize_artifact(a) for a in eld_artifacts]

    # Dashcam artifacts → Samsara deep links (clarifying answer #6).
    dashcam_artifacts = (
        db.query(Artifact)
        .filter(
            Artifact.incident_id == incident_id,
            Artifact.artifact_type.in_(("dashcam_clip", "dashcam_video")),
        )
        .order_by(Artifact.created_at_utc.desc())
        .all()
    )
    samsara_links = [
        _build_samsara_clip_link(
            samsara_vehicle_id=incident.samsara_vehicle_id, artifact=a
        )
        for a in dashcam_artifacts
    ]

    # Related event count for sanity checks in the report header.
    event_count = (
        db.query(Event).filter(Event.incident_id == incident_id).count()
    )

    return CrashPacketRow(
        incident_json=_serialize_incident(incident),
        driver_json=_serialize_driver(driver_obj) if driver_obj else None,
        driver_history_json=driver_history,
        vehicle_json=_serialize_vehicle(vehicle_obj) if vehicle_obj else None,
        trailer_json=_serialize_trailer(trailer_obj) if trailer_obj else None,
        maintenance_json=maintenance,
        eld_logs_json=eld_logs,
        samsara_clip_links_json=samsara_links,
        related_event_count=event_count,
    )
