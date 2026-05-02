"""Repository for maintenance_records (Phase 2)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import MaintenanceRecord


def list_for_asset(
    db: Session,
    *,
    org_id: _uuid.UUID,
    asset_kind: str,
    asset_id: str,
    since_utc: datetime,
) -> list[MaintenanceRecord]:
    """Return maintenance records for one asset since ``since_utc``, newest first."""
    return (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.org_id == org_id,
            MaintenanceRecord.asset_kind == asset_kind,
            MaintenanceRecord.asset_id == asset_id,
            MaintenanceRecord.performed_at_utc >= since_utc,
        )
        .order_by(MaintenanceRecord.performed_at_utc.desc())
        .all()
    )


def list_combined_window(
    db: Session,
    *,
    org_id: _uuid.UUID,
    tractor_asset_id: str | None,
    trailer_asset_id: str | None,
    days: int,
) -> list[MaintenanceRecord]:
    """Combined tractor+trailer maintenance lookup for the crash packet."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    asset_filters = []
    if tractor_asset_id:
        asset_filters.append(("tractor", tractor_asset_id))
    if trailer_asset_id:
        asset_filters.append(("trailer", trailer_asset_id))
    if not asset_filters:
        return []

    out: list[MaintenanceRecord] = []
    for kind, aid in asset_filters:
        out.extend(
            list_for_asset(
                db,
                org_id=org_id,
                asset_kind=kind,
                asset_id=aid,
                since_utc=since,
            )
        )
    out.sort(key=lambda r: r.performed_at_utc, reverse=True)
    return out


def upsert_from_tms(
    db: Session,
    *,
    org_id: _uuid.UUID,
    external_id: str,
    fields: dict[str, Any],
) -> tuple[MaintenanceRecord, bool]:
    """Insert or update a TMS-sourced maintenance record by ``(org_id, external_id)``.

    Required fields when inserting: ``asset_kind`` ('tractor'|'trailer'),
    ``asset_id``, ``performed_at_utc``. Returns ``(record, created)``.
    """
    now = datetime.now(timezone.utc)
    existing = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.org_id == org_id,
            MaintenanceRecord.external_id == external_id,
        )
        .first()
    )
    allowed = {
        "asset_kind",
        "asset_id",
        "performed_at_utc",
        "vendor",
        "summary",
        "mileage",
    }
    clean = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if existing is None:
        for required in ("asset_kind", "asset_id", "performed_at_utc"):
            if required not in clean:
                raise ValueError(
                    f"Cannot insert maintenance_record without {required!r}"
                )
        record = MaintenanceRecord(
            org_id=org_id,
            external_id=external_id,
            source="tms",
            synced_at_utc=now,
            **clean,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record, True

    for k, v in clean.items():
        setattr(existing, k, v)
    existing.source = "tms"
    existing.synced_at_utc = now
    db.commit()
    db.refresh(existing)
    return existing, False
