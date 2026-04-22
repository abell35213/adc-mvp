"""Vehicle CSV import job services."""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ExternalMapping, OrgVehicleRegistry, VehicleImportJob, VehicleQrToken

CANONICAL_HEADER_ALIASES = {
    "unit_number": {"unitnumber", "unit_number", "unit", "trucknumber", "vehicleunit"},
    "vin": {"vin", "vehiclevin"},
    "provider_vehicle_id": {"providervehicleid", "externalid", "providerid"},
    "is_active": {"isactive", "active", "status"},
}


def _normalize_header(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum() or ch == "_")


def _build_header_map(fieldnames: list[str], explicit: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    normalized_to_original = {_normalize_header(name): name for name in fieldnames}

    resolved: dict[str, str] = {}
    for canonical in CANONICAL_HEADER_ALIASES:
        requested = explicit.get(canonical)
        if requested:
            key = _normalize_header(requested)
            original = normalized_to_original.get(key)
            if original is None:
                warnings.append(
                    f"Header mapping for '{canonical}' points to missing column '{requested}'."
                )
                continue
            resolved[canonical] = original
            continue

        for alias in CANONICAL_HEADER_ALIASES[canonical]:
            original = normalized_to_original.get(alias)
            if original:
                resolved[canonical] = original
                break

    if "unit_number" not in resolved:
        warnings.append("Unable to resolve required unitNumber header mapping.")
    return resolved, warnings


def _row_is_active(raw: str | None) -> bool:
    if raw is None:
        return True
    normalized = raw.strip().lower()
    if not normalized:
        return True
    if normalized in {"inactive", "disabled", "false", "0", "no"}:
        return False
    return True


def create_vehicle_import_job(
    db: Session,
    *,
    org_id: uuid.UUID,
    provider: str,
) -> VehicleImportJob:
    now = datetime.now(timezone.utc)
    job = VehicleImportJob(
        org_id=org_id,
        provider=provider.strip(),
        status="pending",
        started_at_utc=now,
        warnings_json=[],
        outcomes_json={"imported": [], "updated": [], "skipped": [], "errored": []},
        summary_json={
            "missing_qr_count": 0,
            "missing_provider_mapping_count": 0,
            "duplicate_like_count": 0,
            "inactive_count": 0,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_vehicle_import_job(
    db: Session,
    *,
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    csv_content: str,
    header_mapping: dict[str, str],
    inactive_unit_numbers: set[str],
) -> VehicleImportJob:
    job = db.query(VehicleImportJob).filter(VehicleImportJob.job_id == job_id, VehicleImportJob.org_id == org_id).first()
    if job is None:
        raise ValueError("job_not_found")

    job.status = "running"
    db.add(job)
    db.commit()

    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        if reader.fieldnames is None:
            raise ValueError("CSV missing headers")

        resolved_headers, mapping_warnings = _build_header_map(reader.fieldnames, header_mapping)
        warnings = list(mapping_warnings)

        outcomes = {"imported": [], "updated": [], "skipped": [], "errored": []}
        summary = {
            "missing_qr_count": 0,
            "missing_provider_mapping_count": 0,
            "duplicate_like_count": 0,
            "inactive_count": 0,
        }

        existing_by_unit = {
            row.unit_number.lower(): row
            for row in db.query(OrgVehicleRegistry).filter(OrgVehicleRegistry.org_id == org_id).all()
        }
        unit_to_qr = {
            row.adc_vehicle_id.lower()
            for row in db.query(VehicleQrToken)
            .filter(VehicleQrToken.org_id == org_id, VehicleQrToken.status == "active")
            .all()
        }
        provider_mapped_units = {
            row.internal_entity_id.lower()
            for row in db.query(ExternalMapping)
            .filter(
                ExternalMapping.org_id == org_id,
                ExternalMapping.internal_entity_type == "vehicle",
                ExternalMapping.status == "active",
            )
            .all()
        }

        seen_units: set[str] = set()
        vin_to_units: defaultdict[str, set[str]] = defaultdict(set)
        staged_rows: list[dict[str, str | bool | None]] = []

        for line_no, row in enumerate(reader, start=2):
            unit_col = resolved_headers.get("unit_number")
            vin_col = resolved_headers.get("vin")
            provider_vehicle_col = resolved_headers.get("provider_vehicle_id")
            active_col = resolved_headers.get("is_active")

            raw_unit = (row.get(unit_col, "") if unit_col else "") or ""
            unit_number = raw_unit.strip()
            vin = ((row.get(vin_col, "") if vin_col else "") or "").strip() or None
            provider_vehicle_id = (
                ((row.get(provider_vehicle_col, "") if provider_vehicle_col else "") or "").strip()
                or None
            )
            row_active = _row_is_active(row.get(active_col) if active_col else None)
            if unit_number.lower() in inactive_unit_numbers:
                row_active = False

            if not unit_number:
                outcomes["errored"].append(f"line {line_no}: unitNumber is required")
                continue

            lowered_unit = unit_number.lower()
            if lowered_unit in seen_units:
                outcomes["errored"].append(f"line {line_no}: duplicate unitNumber '{unit_number}' in CSV")
                continue
            seen_units.add(lowered_unit)

            if vin:
                vin_to_units[vin].add(lowered_unit)

            staged_rows.append(
                {
                    "line_no": str(line_no),
                    "unit_number": unit_number,
                    "vin": vin,
                    "provider_vehicle_id": provider_vehicle_id,
                    "is_active": row_active,
                }
            )

        for vin, units in vin_to_units.items():
            if len(units) > 1:
                warnings.append(f"VIN '{vin}' appears on multiple unitNumber values.")
                summary["duplicate_like_count"] += len(units)

        for staged in staged_rows:
            unit_number = str(staged["unit_number"])
            lowered_unit = unit_number.lower()
            existing = existing_by_unit.get(lowered_unit)
            if existing is None:
                existing = OrgVehicleRegistry(
                    org_id=org_id,
                    unit_number=unit_number,
                    vin=staged["vin"],
                    provider=job.provider,
                    provider_vehicle_id=staged["provider_vehicle_id"],
                    is_active=bool(staged["is_active"]),
                )
                db.add(existing)
                outcomes["imported"].append(unit_number)
                existing_by_unit[lowered_unit] = existing
            else:
                existing.vin = staged["vin"]
                existing.provider = job.provider
                existing.provider_vehicle_id = staged["provider_vehicle_id"]
                existing.is_active = bool(staged["is_active"])
                outcomes["updated"].append(unit_number)

            if not bool(staged["is_active"]):
                summary["inactive_count"] += 1
                outcomes["skipped"].append(f"{unit_number}: inactive")

            if lowered_unit not in unit_to_qr:
                summary["missing_qr_count"] += 1
            if lowered_unit not in provider_mapped_units:
                summary["missing_provider_mapping_count"] += 1

        job.records_total = len(staged_rows)
        job.records_processed = len(staged_rows)
        job.records_imported = len(outcomes["imported"])
        job.records_updated = len(outcomes["updated"])
        job.records_skipped = len(outcomes["skipped"])
        job.records_errored = len(outcomes["errored"])
        job.warnings_json = warnings
        job.outcomes_json = outcomes
        job.summary_json = summary
        job.status = "succeeded" if not outcomes["errored"] else "failed"
        job.completed_at_utc = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at_utc = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
