"""Repository for dispatch_instructions (Phase 3)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DispatchInstruction


# Allowlist of attributes the TMS sync (and manual-entry API) may write.
# Mirrors the model column list — keeps writes forward-compatible with
# vendor field maps that include extra unknown columns.
ALLOWED_FIELDS = {
    "adc_driver_id",
    "adc_vehicle_id",
    "adc_trailer_id",
    "incident_id",
    "dispatch_id",
    "load_number",
    "dispatched_by",
    "dispatched_at_utc",
    "pickup_appointment_at_utc",
    "delivery_appointment_at_utc",
    "eta_at_utc",
    "origin_address",
    "destination_address",
    "hos_remaining_drive_minutes",
    "hos_remaining_duty_minutes",
    "forced_dispatch_flag",
    "notes",
}


def get_by_external_id(
    db: Session, *, org_id: _uuid.UUID, external_id: str
) -> DispatchInstruction | None:
    return (
        db.query(DispatchInstruction)
        .filter(
            DispatchInstruction.org_id == org_id,
            DispatchInstruction.external_id == external_id,
        )
        .first()
    )


def get_by_id(
    db: Session, *, org_id: _uuid.UUID, dispatch_id: _uuid.UUID
) -> DispatchInstruction | None:
    return (
        db.query(DispatchInstruction)
        .filter(
            DispatchInstruction.org_id == org_id,
            DispatchInstruction.id == dispatch_id,
        )
        .first()
    )


def list_for_org(
    db: Session,
    *,
    org_id: _uuid.UUID,
    limit: int = 100,
) -> list[DispatchInstruction]:
    return (
        db.query(DispatchInstruction)
        .filter(DispatchInstruction.org_id == org_id)
        .order_by(DispatchInstruction.dispatched_at_utc.desc().nullslast())
        .limit(limit)
        .all()
    )


def create_manual(
    db: Session, *, org_id: _uuid.UUID, fields: dict[str, Any]
) -> DispatchInstruction:
    """Insert a manually-entered dispatch instruction (``source='manual'``)."""
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
    instruction = DispatchInstruction(org_id=org_id, source="manual", **clean)
    db.add(instruction)
    db.commit()
    db.refresh(instruction)
    return instruction


def update_manual(
    db: Session,
    *,
    instruction: DispatchInstruction,
    fields: dict[str, Any],
) -> DispatchInstruction:
    """Update fields on an existing manual or TMS-synced dispatch instruction.

    Note: this does *not* change ``source`` — manually editing a
    TMS-sourced row keeps it tagged ``tms`` so the next sync can re-apply
    upstream changes if desired. The API layer can flip ``source`` if it
    really wants to fork a row off from sync.
    """
    for k, v in fields.items():
        if k in ALLOWED_FIELDS:
            setattr(instruction, k, v)
    db.commit()
    db.refresh(instruction)
    return instruction


def upsert_from_tms(
    db: Session,
    *,
    org_id: _uuid.UUID,
    external_id: str,
    fields: dict[str, Any],
) -> tuple[DispatchInstruction, bool]:
    """Insert or update a TMS-sourced dispatch keyed on ``(org_id, external_id)``.

    Manually-entered rows have ``external_id IS NULL`` and are never touched.
    """
    now = datetime.now(timezone.utc)
    existing = get_by_external_id(db, org_id=org_id, external_id=external_id)
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS and v is not None}

    if existing is None:
        instruction = DispatchInstruction(
            org_id=org_id,
            external_id=external_id,
            source="tms",
            synced_at_utc=now,
            **clean,
        )
        db.add(instruction)
        db.commit()
        db.refresh(instruction)
        return instruction, True

    for k, v in clean.items():
        setattr(existing, k, v)
    existing.source = "tms"
    existing.synced_at_utc = now
    db.commit()
    db.refresh(existing)
    return existing, False
