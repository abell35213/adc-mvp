"""Repository for weigh_station_reports (Phase 3)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import WeighStationReport


ALLOWED_FIELDS = {
    "adc_vehicle_id",
    "adc_trailer_id",
    "dispatch_instruction_id",
    "incident_id",
    "weighed_at_utc",
    "station_name",
    "station_location",
    "ticket_number",
    "gross_weight_lb",
    "steer_axle_weight_lb",
    "drive_axle_weight_lb",
    "trailer_axle_weight_lb",
    "legal_limit_lb",
    "is_over_legal_limit",
    "result",
    "citation_text",
    "inspector_name",
    "doc_artifact_id",
}


def _coerce_over_limit(fields: dict[str, Any]) -> None:
    """Compute ``is_over_legal_limit`` from gross + legal limit when not given."""
    if "is_over_legal_limit" in fields:
        return
    gross = fields.get("gross_weight_lb")
    limit = fields.get("legal_limit_lb")
    if gross is not None and limit is not None:
        try:
            fields["is_over_legal_limit"] = int(gross) > int(limit)
        except (TypeError, ValueError):
            pass


def get_by_external_id(
    db: Session, *, org_id: _uuid.UUID, external_id: str
) -> WeighStationReport | None:
    return (
        db.query(WeighStationReport)
        .filter(
            WeighStationReport.org_id == org_id,
            WeighStationReport.external_id == external_id,
        )
        .first()
    )


def get_by_id(
    db: Session, *, org_id: _uuid.UUID, report_id: _uuid.UUID
) -> WeighStationReport | None:
    return (
        db.query(WeighStationReport)
        .filter(
            WeighStationReport.org_id == org_id,
            WeighStationReport.id == report_id,
        )
        .first()
    )


def list_for_org(
    db: Session,
    *,
    org_id: _uuid.UUID,
    limit: int = 100,
) -> list[WeighStationReport]:
    return (
        db.query(WeighStationReport)
        .filter(WeighStationReport.org_id == org_id)
        .order_by(WeighStationReport.weighed_at_utc.desc().nullslast())
        .limit(limit)
        .all()
    )


def create_manual(
    db: Session, *, org_id: _uuid.UUID, fields: dict[str, Any]
) -> WeighStationReport:
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
    _coerce_over_limit(clean)
    report = WeighStationReport(org_id=org_id, source="manual", **clean)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def update_manual(
    db: Session,
    *,
    report: WeighStationReport,
    fields: dict[str, Any],
) -> WeighStationReport:
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
    # Recompute over-limit if either gross or limit is being changed and the
    # caller didn't pass an explicit override.
    if (
        "is_over_legal_limit" not in clean
        and ("gross_weight_lb" in clean or "legal_limit_lb" in clean)
    ):
        merged = {
            "gross_weight_lb": clean.get("gross_weight_lb", report.gross_weight_lb),
            "legal_limit_lb": clean.get("legal_limit_lb", report.legal_limit_lb),
        }
        _coerce_over_limit(merged)
        if "is_over_legal_limit" in merged:
            clean["is_over_legal_limit"] = merged["is_over_legal_limit"]
    for k, v in clean.items():
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
) -> tuple[WeighStationReport, bool]:
    now = datetime.now(timezone.utc)
    existing = get_by_external_id(db, org_id=org_id, external_id=external_id)
    clean = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS and v is not None}
    _coerce_over_limit(clean)

    if existing is None:
        report = WeighStationReport(
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
