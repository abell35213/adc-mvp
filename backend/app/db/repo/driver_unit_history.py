"""Repository for ``driver_unit_history`` (slip-seating-aware driver→unit history).

The TMS sync writes via :func:`upsert_from_tms`. The capture service
reads via :func:`list_active_for_driver_in_window`, falling back to a
synthesized view of :class:`DriverVehicleAssignment` rows when no TMS
history exists.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Driver, DriverUnitHistory, DriverVehicleAssignment

# Allowlist of attributes the TMS sync (and manual-entry API) may write.
ALLOWED_FIELDS = {
    "driver_id",
    "adc_driver_id",
    "unit_kind",
    "adc_vehicle_id",
    "unit_number",
    "vin",
    "license_plate",
    "license_state",
    "started_at_utc",
    "ended_at_utc",
    "source",
    "source_record_ref",
    "confidence",
    "confidence_reason",
}


def _classify_confidence(fields: dict[str, Any]) -> tuple[str, str]:
    """Return ``(confidence, reason)`` per the slip-seating rules.

    HIGH   = TMS-sourced, has VIN OR unit_number, has both started/ended,
             AND ``driver_id`` resolved (Driver row matched).
    MEDIUM = TMS but open-ended, OR missing one of (VIN, unit_number).
    LOW    = derived_from_assignment, manual entry, OR unresolved driver.
    """
    source = fields.get("source") or "tms"
    if source in {"manual", "derived_from_assignment"}:
        return "low", f"source={source}"

    has_unit_id = bool(fields.get("vin") or fields.get("unit_number"))
    has_window = bool(fields.get("started_at_utc") and fields.get("ended_at_utc"))
    has_driver = bool(fields.get("driver_id"))

    if not has_driver:
        return "low", "driver_unresolved"

    if has_unit_id and has_window:
        return "high", "tms_window_and_unit_id"
    if has_unit_id or has_window:
        return "medium", "tms_partial"
    return "medium", "tms_minimal"


def _resolve_driver_id(
    db: Session, *, org_id: _uuid.UUID, adc_driver_id: str | None
) -> _uuid.UUID | None:
    """Try to find a ``Driver`` row from a TMS adc_driver_id (best-effort)."""
    if not adc_driver_id:
        return None
    # We don't have a strong adc_driver_id ↔ Driver mapping; fall back to
    # phone-or-display-name only when explicitly stored. For now, just
    # return None; the capture service will treat unresolved as LOW.
    _ = db
    _ = org_id
    return None


def upsert_from_tms(
    db: Session,
    *,
    org_id: _uuid.UUID,
    external_id: str,
    fields: dict[str, Any],
) -> tuple[DriverUnitHistory, bool]:
    """Insert or update a TMS-sourced driver_unit_history row keyed on
    ``(org_id, external_id)``.

    Manually-entered rows have ``external_id IS NULL`` and are never
    touched here.
    """
    now = datetime.now(timezone.utc)
    existing = (
        db.query(DriverUnitHistory)
        .filter(
            DriverUnitHistory.org_id == org_id,
            DriverUnitHistory.external_id == external_id,
        )
        .first()
    )
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS and v is not None}
    if "started_at_utc" not in clean:
        # Fallback: TMS row with no start; can't be matched against an
        # inspection date — skip rather than persist an invalid row.
        if existing is None:
            raise ValueError("started_at_utc is required for driver_unit_history")
        clean["started_at_utc"] = existing.started_at_utc

    # Resolve internal driver_id when possible.
    if "driver_id" not in clean and clean.get("adc_driver_id"):
        resolved = _resolve_driver_id(
            db, org_id=org_id, adc_driver_id=clean.get("adc_driver_id")
        )
        if resolved is not None:
            clean["driver_id"] = resolved

    # Default unit_kind so the model NOT NULL constraint is satisfied.
    clean.setdefault("unit_kind", "tractor")

    confidence, reason = _classify_confidence(clean)
    clean.setdefault("confidence", confidence)
    clean.setdefault("confidence_reason", reason)
    clean.setdefault("source", "tms")

    if existing is None:
        row = DriverUnitHistory(
            org_id=org_id,
            external_id=external_id,
            synced_at_utc=now,
            **clean,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row, True

    for k, v in clean.items():
        setattr(existing, k, v)
    existing.source = clean.get("source", "tms")
    existing.synced_at_utc = now
    db.commit()
    db.refresh(existing)
    return existing, False


def list_active_for_driver_in_window(
    db: Session,
    *,
    org_id: _uuid.UUID,
    driver_id: _uuid.UUID,
    window_start_utc: datetime,
) -> list[DriverUnitHistory]:
    """Return all driver_unit_history rows whose ``[started, ended]`` window
    overlaps ``[window_start_utc, now]``.
    """
    rows = (
        db.query(DriverUnitHistory)
        .filter(
            DriverUnitHistory.org_id == org_id,
            DriverUnitHistory.driver_id == driver_id,
        )
        .all()
    )
    out: list[DriverUnitHistory] = []
    for r in rows:
        ended = r.ended_at_utc
        if ended is not None and ended < window_start_utc:
            continue
        out.append(r)
    return out


def derive_from_assignments(
    db: Session,
    *,
    org_id: _uuid.UUID,
    driver_id: _uuid.UUID,
) -> list[DriverUnitHistory]:
    """Synthesize transient (un-persisted) DriverUnitHistory rows from
    :class:`DriverVehicleAssignment`.

    Used as a low-confidence fallback when no TMS history is mapped.
    The returned rows are *not* committed to the DB — the capture service
    only needs them in-memory to feed the matcher.
    """
    assignments = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.org_id == org_id,
            DriverVehicleAssignment.driver_id == driver_id,
        )
        .all()
    )
    rows: list[DriverUnitHistory] = []
    for a in assignments:
        rows.append(
            DriverUnitHistory(
                id=_uuid.uuid4(),
                org_id=org_id,
                driver_id=driver_id,
                adc_driver_id=None,
                unit_kind="tractor",
                adc_vehicle_id=a.adc_vehicle_id,
                unit_number=None,
                vin=None,
                license_plate=None,
                license_state=None,
                started_at_utc=a.assigned_at_utc,
                ended_at_utc=a.unassigned_at_utc,
                source="derived_from_assignment",
                confidence="low",
                confidence_reason="derived_from_driver_vehicle_assignment",
            )
        )
    return rows


__all__ = [
    "ALLOWED_FIELDS",
    "Driver",
    "derive_from_assignments",
    "list_active_for_driver_in_window",
    "upsert_from_tms",
]
