"""Repository for trailer rows (Phase 2)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Trailer


def get_by_external_id(
    db: Session, *, org_id: _uuid.UUID, external_id: str
) -> Trailer | None:
    return (
        db.query(Trailer)
        .filter(Trailer.org_id == org_id, Trailer.external_id == external_id)
        .first()
    )


def get_by_adc_trailer_id(
    db: Session, *, org_id: _uuid.UUID, adc_trailer_id: str
) -> Trailer | None:
    return (
        db.query(Trailer)
        .filter(
            Trailer.org_id == org_id,
            Trailer.adc_trailer_id == adc_trailer_id,
        )
        .first()
    )


def upsert_from_tms(
    db: Session,
    *,
    org_id: _uuid.UUID,
    external_id: str,
    fields: dict[str, Any],
) -> tuple[Trailer, bool]:
    """Insert or update a TMS-sourced trailer keyed on ``(org_id, external_id)``.

    Returns ``(trailer, created)`` where ``created`` is True iff a new row
    was inserted. Always sets ``source='tms'`` and stamps ``synced_at_utc``.
    Unknown ``fields`` keys are ignored (forward-compatible).
    """
    now = datetime.now(timezone.utc)
    existing = get_by_external_id(db, org_id=org_id, external_id=external_id)
    allowed = {
        "adc_trailer_id",
        "vin",
        "make",
        "model",
        "year",
        "plate",
        "last_inspection_at_utc",
    }
    clean = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if existing is None:
        # adc_trailer_id is required; fall back to external_id when the TMS
        # field map didn't supply one explicitly.
        adc_trailer_id = clean.pop("adc_trailer_id", external_id)
        trailer = Trailer(
            org_id=org_id,
            adc_trailer_id=adc_trailer_id,
            external_id=external_id,
            source="tms",
            synced_at_utc=now,
            **clean,
        )
        db.add(trailer)
        db.commit()
        db.refresh(trailer)
        return trailer, True

    for k, v in clean.items():
        setattr(existing, k, v)
    existing.source = "tms"
    existing.synced_at_utc = now
    db.commit()
    db.refresh(existing)
    return existing, False
