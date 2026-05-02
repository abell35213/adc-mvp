"""Repository for FMCSA MCMIS snapshots / inspections / per-incident attribution."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.db.models import (
    FmcsaInspection,
    FmcsaInspectionSnapshot,
    IncidentDriverViolationHistory,
)


# ── Snapshots ───────────────────────────────────────────────────────


def get_latest_succeeded_snapshot(
    db: Session, *, org_id: _uuid.UUID
) -> FmcsaInspectionSnapshot | None:
    """Return the most-recent succeeded snapshot for an org, or ``None``."""
    return (
        db.query(FmcsaInspectionSnapshot)
        .filter(
            FmcsaInspectionSnapshot.org_id == org_id,
            FmcsaInspectionSnapshot.status == "succeeded",
            FmcsaInspectionSnapshot.is_stale.is_(False),
        )
        .order_by(FmcsaInspectionSnapshot.fetched_at_utc.desc())
        .first()
    )


def is_snapshot_fresh(
    snapshot: FmcsaInspectionSnapshot, *, ttl_hours: int, now: datetime | None = None
) -> bool:
    """True when the snapshot is within ``ttl_hours`` of being usable."""
    if snapshot is None:
        return False
    now = now or datetime.now(timezone.utc)
    fetched = snapshot.fetched_at_utc
    if fetched is None:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return (now - fetched) <= timedelta(hours=ttl_hours)


def create_snapshot(
    db: Session,
    *,
    org_id: _uuid.UUID,
    usdot_number: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
    record_count: int,
    status: str = "succeeded",
    error_json: dict[str, Any] | None = None,
) -> FmcsaInspectionSnapshot:
    snapshot = FmcsaInspectionSnapshot(
        org_id=org_id,
        usdot_number=usdot_number,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        record_count=int(record_count),
        status=status,
        error_json=error_json or {},
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def mark_snapshots_stale(db: Session, *, org_id: _uuid.UUID) -> int:
    """Flip all current succeeded snapshots for an org to ``is_stale=True``."""
    affected = (
        db.query(FmcsaInspectionSnapshot)
        .filter(
            FmcsaInspectionSnapshot.org_id == org_id,
            FmcsaInspectionSnapshot.is_stale.is_(False),
        )
        .all()
    )
    for s in affected:
        s.is_stale = True
    db.commit()
    return len(affected)


# ── Inspections ─────────────────────────────────────────────────────


def upsert_inspections(
    db: Session,
    *,
    snapshot: FmcsaInspectionSnapshot,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Insert (or update by ``(org_id, report_number)``) FMCSA inspection rows."""
    count = 0
    org_id = snapshot.org_id
    for row in rows:
        report_number = (row.get("report_number") or "").strip()
        if not report_number:
            continue
        existing = (
            db.query(FmcsaInspection)
            .filter(
                FmcsaInspection.org_id == org_id,
                FmcsaInspection.report_number == report_number,
            )
            .first()
        )
        target = existing or FmcsaInspection(
            org_id=org_id,
            snapshot_id=snapshot.snapshot_id,
            report_number=report_number,
            usdot_number=snapshot.usdot_number,
        )
        target.snapshot_id = snapshot.snapshot_id
        target.usdot_number = row.get("usdot_number") or snapshot.usdot_number
        target.inspection_date_utc = row.get("inspection_date_utc")
        target.report_state = row.get("report_state")
        target.vehicle_vin = row.get("vehicle_vin")
        target.vehicle_license_plate = row.get("vehicle_license_plate")
        target.vehicle_license_state = row.get("vehicle_license_state")
        target.unit_type = row.get("unit_type") or "other"
        target.inspection_level = row.get("inspection_level")
        target.oos_total = int(row.get("oos_total") or 0)
        target.violation_count = int(row.get("violation_count") or 0)
        target.violations_json = row.get("violations_json") or []
        target.raw_json = row.get("raw_json") or {}
        if existing is None:
            db.add(target)
        count += 1
    db.commit()
    return count


def list_inspections_for_snapshot(
    db: Session, *, snapshot_id: _uuid.UUID
) -> list[FmcsaInspection]:
    return (
        db.query(FmcsaInspection)
        .filter(FmcsaInspection.snapshot_id == snapshot_id)
        .all()
    )


def list_inspections_for_org(
    db: Session,
    *,
    org_id: _uuid.UUID,
    since_utc: datetime | None = None,
    until_utc: datetime | None = None,
) -> list[FmcsaInspection]:
    query = db.query(FmcsaInspection).filter(FmcsaInspection.org_id == org_id)
    if since_utc is not None:
        query = query.filter(FmcsaInspection.inspection_date_utc >= since_utc)
    if until_utc is not None:
        query = query.filter(FmcsaInspection.inspection_date_utc <= until_utc)
    return query.order_by(FmcsaInspection.inspection_date_utc.desc()).all()


# ── Per-incident attribution ────────────────────────────────────────


def replace_incident_attributions(
    db: Session,
    *,
    incident_id: _uuid.UUID,
    matches: Iterable[dict[str, Any]],
) -> int:
    """Wipe and re-insert ``incident_driver_violation_history`` for an incident.

    ``matches`` items are dicts with keys: ``inspection_id``,
    ``unit_history_id``, ``driver_id``, ``match_basis``,
    ``match_confidence``, ``included_in_brief``, ``excluded_reason``.
    """
    db.query(IncidentDriverViolationHistory).filter(
        IncidentDriverViolationHistory.incident_id == incident_id
    ).delete()
    count = 0
    for m in matches:
        row = IncidentDriverViolationHistory(
            incident_id=incident_id,
            inspection_id=m["inspection_id"],
            driver_id=m.get("driver_id"),
            unit_history_id=m.get("unit_history_id"),
            match_basis=m["match_basis"],
            match_confidence=m["match_confidence"],
            included_in_brief=bool(m.get("included_in_brief", False)),
            excluded_reason=m.get("excluded_reason"),
        )
        db.add(row)
        count += 1
    db.commit()
    return count


def list_violation_history_for_incident(
    db: Session,
    incident_id: _uuid.UUID,
    *,
    include_low_confidence: bool = False,
) -> list[tuple[IncidentDriverViolationHistory, FmcsaInspection]]:
    """Return ``(link, inspection)`` pairs for an incident, newest-first."""
    query = (
        db.query(IncidentDriverViolationHistory, FmcsaInspection)
        .join(
            FmcsaInspection,
            FmcsaInspection.inspection_id
            == IncidentDriverViolationHistory.inspection_id,
        )
        .filter(IncidentDriverViolationHistory.incident_id == incident_id)
    )
    if not include_low_confidence:
        query = query.filter(
            IncidentDriverViolationHistory.included_in_brief.is_(True)
        )
    query = query.order_by(FmcsaInspection.inspection_date_utc.desc())
    return query.all()


def get_meta_for_incident(
    db: Session, incident_id: _uuid.UUID
) -> dict[str, Any]:
    """Counts + last-refreshed metadata for the brief footer."""
    rows = (
        db.query(IncidentDriverViolationHistory)
        .filter(IncidentDriverViolationHistory.incident_id == incident_id)
        .all()
    )
    included = sum(1 for r in rows if r.included_in_brief)
    excluded_low = sum(
        1
        for r in rows
        if r.match_confidence == "low" and not r.included_in_brief
    )
    snapshot = (
        db.query(FmcsaInspectionSnapshot)
        .join(
            FmcsaInspection,
            FmcsaInspection.snapshot_id == FmcsaInspectionSnapshot.snapshot_id,
        )
        .join(
            IncidentDriverViolationHistory,
            IncidentDriverViolationHistory.inspection_id
            == FmcsaInspection.inspection_id,
        )
        .filter(IncidentDriverViolationHistory.incident_id == incident_id)
        .order_by(FmcsaInspectionSnapshot.fetched_at_utc.desc())
        .first()
    )
    return {
        "total_inspections_pulled": len(rows),
        "included_count": included,
        "low_confidence_excluded_count": excluded_low,
        "last_refreshed_at_utc": (
            snapshot.fetched_at_utc.isoformat() if snapshot else None
        ),
        "snapshot_status": snapshot.status if snapshot else None,
    }
