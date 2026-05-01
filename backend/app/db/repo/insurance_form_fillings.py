"""Repository for insurance_form_fillings (Phase 3)."""

from __future__ import annotations

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import InsuranceFormFilling


def get_filling(
    db: Session, filling_id: _uuid.UUID
) -> InsuranceFormFilling | None:
    return (
        db.query(InsuranceFormFilling)
        .filter(InsuranceFormFilling.id == filling_id)
        .first()
    )


def find_existing(
    db: Session,
    *,
    incident_id: _uuid.UUID,
    template_id: _uuid.UUID,
    payload_hash: str,
) -> InsuranceFormFilling | None:
    """Idempotency lookup keyed on ``(incident_id, template_id, payload_hash)``."""
    return (
        db.query(InsuranceFormFilling)
        .filter(
            InsuranceFormFilling.incident_id == incident_id,
            InsuranceFormFilling.template_id == template_id,
            InsuranceFormFilling.payload_hash == payload_hash,
        )
        .first()
    )


def list_for_incident(
    db: Session, incident_id: _uuid.UUID
) -> list[InsuranceFormFilling]:
    return (
        db.query(InsuranceFormFilling)
        .filter(InsuranceFormFilling.incident_id == incident_id)
        .order_by(InsuranceFormFilling.created_at_utc.desc())
        .all()
    )
