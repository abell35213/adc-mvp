"""Repository for loading_dock_reports (Phase 3)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Artifact, LoadingDockReport


ALLOWED_FIELDS = {
    "adc_trailer_id",
    "adc_vehicle_id",
    "dispatch_instruction_id",
    "incident_id",
    "loaded_at_utc",
    "facility_name",
    "facility_address",
    "commodity",
    "pieces",
    "gross_weight_lb",
    "net_weight_lb",
    "seal_number",
    "securement_method",
    "weight_distribution_notes",
    "is_overloaded",
    "is_improperly_loaded",
    "loaded_by",
    "dock_supervisor",
    "signature_artifact_id",
}


def get_by_external_id(
    db: Session, *, org_id: _uuid.UUID, external_id: str
) -> LoadingDockReport | None:
    return (
        db.query(LoadingDockReport)
        .filter(
            LoadingDockReport.org_id == org_id,
            LoadingDockReport.external_id == external_id,
        )
        .first()
    )


def get_by_id(
    db: Session, *, org_id: _uuid.UUID, report_id: _uuid.UUID
) -> LoadingDockReport | None:
    return (
        db.query(LoadingDockReport)
        .filter(
            LoadingDockReport.org_id == org_id,
            LoadingDockReport.id == report_id,
        )
        .first()
    )


def list_for_org(
    db: Session,
    *,
    org_id: _uuid.UUID,
    limit: int = 100,
) -> list[LoadingDockReport]:
    return (
        db.query(LoadingDockReport)
        .filter(LoadingDockReport.org_id == org_id)
        .order_by(LoadingDockReport.loaded_at_utc.desc().nullslast())
        .limit(limit)
        .all()
    )


def list_photos(
    db: Session, *, loading_dock_report_id: _uuid.UUID
) -> list[Artifact]:
    """Return the photo (and signature) artifacts attached to a dock report."""
    return (
        db.query(Artifact)
        .filter(Artifact.loading_dock_report_id == loading_dock_report_id)
        .order_by(Artifact.created_at_utc.asc())
        .all()
    )


def attach_artifact(
    db: Session,
    *,
    artifact: Artifact,
    loading_dock_report_id: _uuid.UUID,
) -> Artifact:
    """Link an existing :class:`Artifact` row to a loading-dock report.

    Used by the artifact upload flow to many-to-one link dock photos.
    """
    artifact.loading_dock_report_id = loading_dock_report_id
    db.commit()
    db.refresh(artifact)
    return artifact


def create_manual(
    db: Session, *, org_id: _uuid.UUID, fields: dict[str, Any]
) -> LoadingDockReport:
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
    report = LoadingDockReport(org_id=org_id, source="manual", **clean)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def update_manual(
    db: Session,
    *,
    report: LoadingDockReport,
    fields: dict[str, Any],
) -> LoadingDockReport:
    for k, v in fields.items():
        if k in ALLOWED_FIELDS:
            setattr(report, k, v)
    db.commit()
    db.refresh(report)
    return report


def upsert_from_tms(
    db: Session,
    *,
    org_id: _uuid.UUID,
    external_id: str,
    fields: dict[str, Any],
) -> tuple[LoadingDockReport, bool]:
    now = datetime.now(timezone.utc)
    existing = get_by_external_id(db, org_id=org_id, external_id=external_id)
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS and v is not None}

    if existing is None:
        report = LoadingDockReport(
            org_id=org_id,
            external_id=external_id,
            source="tms",
            synced_at_utc=now,
            **clean,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report, True

    for k, v in clean.items():
        setattr(existing, k, v)
    existing.source = "tms"
    existing.synced_at_utc = now
    db.commit()
    db.refresh(existing)
    return existing, False
