"""Driver CSV import job services."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence, cast

from sqlalchemy.orm import Session

from app.db.models import (
    Driver,
    DriverImportJob,
    DriverVehicleAssignment,
    ExternalMapping,
)
from app.services.phone_normalize import normalize_phone

CANONICAL_HEADER_ALIASES = {
    "first_name": {"firstname", "first_name", "first"},
    "last_name": {"lastname", "last_name", "last"},
    "phone": {"phone", "mobile", "mobilephone", "phone_e164"},
    "vehicle_id": {
        "vehicleid",
        "vehicle_id",
        "adcvehicleid",
        "unitnumber",
        "unit_number",
    },
    "provider_driver_id": {
        "providerdriverid",
        "provider_driver_id",
        "externaldriverid",
    },
    "is_active": {"isactive", "active", "status"},
}


def _normalize_header(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum() or ch == "_")


def _build_header_map(
    fieldnames: Sequence[str], explicit: dict[str, str]
) -> tuple[dict[str, str], list[str]]:
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


def create_driver_import_job(
    db: Session,
    *,
    org_id: uuid.UUID,
    provider: str,
) -> DriverImportJob:
    now = datetime.now(timezone.utc)
    job = DriverImportJob(
        org_id=org_id,
        provider=provider.strip(),
        status="pending",
        started_at_utc=now,
        warnings_json=[],
        outcomes_json={
            "imported": [],
            "updated": [],
            "skipped": [],
            "errored": [],
            "invalid_phone": [],
            "duplicate_warning": [],
            "missing_assignment_or_mapping": [],
            "needs_review": [],
        },
        summary_json={
            "invalid_phone_count": 0,
            "duplicate_warning_count": 0,
            "missing_assignment_count": 0,
            "missing_external_mapping_count": 0,
            "needs_review_count": 0,
            "inactive_count": 0,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_driver_import_job(
    db: Session,
    *,
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    csv_content: str,
    header_mapping: dict[str, str],
    inactive_phones: set[str],
) -> DriverImportJob:
    job = cast(Any, (
        db.query(DriverImportJob)
        .filter(DriverImportJob.job_id == job_id, DriverImportJob.org_id == org_id)
        .first()
    ))
    if job is None:
        raise ValueError("job_not_found")

    job.status = "running"
    db.add(job)
    db.commit()

    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        if reader.fieldnames is None:
            raise ValueError("CSV missing headers")

        resolved_headers, mapping_warnings = _build_header_map(
            reader.fieldnames, header_mapping
        )
        warnings = list(mapping_warnings)

        outcomes: dict[str, list[str]] = {
            "imported": [],
            "updated": [],
            "skipped": [],
            "errored": [],
            "invalid_phone": [],
            "duplicate_warning": [],
            "missing_assignment_or_mapping": [],
            "needs_review": [],
        }
        summary = {
            "invalid_phone_count": 0,
            "duplicate_warning_count": 0,
            "missing_assignment_count": 0,
            "missing_external_mapping_count": 0,
            "needs_review_count": 0,
            "inactive_count": 0,
        }

        existing_driver_rows = cast(list[Any], db.query(Driver).all())
        existing_by_phone = {str(row.phone_e164): row for row in existing_driver_rows if row.phone_e164}
        assignment_rows = cast(list[Any], db.query(DriverVehicleAssignment)
            .filter(
                DriverVehicleAssignment.org_id == org_id,
                DriverVehicleAssignment.unassigned_at_utc.is_(None),
            )
            .all())
        assigned_driver_ids = {str(row.driver_id) for row in assignment_rows}
        mapped_driver_rows = cast(list[Any], db.query(ExternalMapping)
            .filter(
                ExternalMapping.org_id == org_id,
                ExternalMapping.internal_entity_type == "driver",
                ExternalMapping.status == "active",
            )
            .all())
        provider_mapped_driver_ids = {str(row.internal_entity_id).lower() for row in mapped_driver_rows}

        seen_phone_to_line: dict[str, int] = {}
        staged_rows: list[dict[str, str | bool | None]] = []

        for line_no, row in enumerate(reader, start=2):
            first_col = resolved_headers.get("first_name")
            last_col = resolved_headers.get("last_name")
            phone_col = resolved_headers.get("phone")
            provider_driver_col = resolved_headers.get("provider_driver_id")
            active_col = resolved_headers.get("is_active")

            first_name = ((row.get(first_col, "") if first_col else "") or "").strip()
            last_name = ((row.get(last_col, "") if last_col else "") or "").strip()
            raw_phone = ((row.get(phone_col, "") if phone_col else "") or "").strip()
            provider_driver_id = (
                (row.get(provider_driver_col, "") if provider_driver_col else "") or ""
            ).strip() or None
            row_active = _row_is_active(row.get(active_col) if active_col else None)

            if not first_name:
                outcomes["errored"].append(f"line {line_no}: firstName is required")
                continue
            if not last_name:
                outcomes["errored"].append(f"line {line_no}: lastName is required")
                continue
            if not raw_phone:
                outcomes["errored"].append(f"line {line_no}: mobile phone is required")
                continue

            try:
                phone_e164 = normalize_phone(raw_phone)
            except ValueError:
                outcomes["errored"].append(
                    f"line {line_no}: invalid mobile phone '{raw_phone}'"
                )
                outcomes["invalid_phone"].append(f"line {line_no}: {raw_phone}")
                summary["invalid_phone_count"] += 1
                summary["needs_review_count"] += 1
                outcomes["needs_review"].append(f"line {line_no}: invalid mobile phone")
                continue

            if phone_e164 in seen_phone_to_line:
                first_seen = seen_phone_to_line[phone_e164]
                message = f"line {line_no}: duplicate mobile phone '{phone_e164}' (already used on line {first_seen})"
                outcomes["errored"].append(message)
                outcomes["duplicate_warning"].append(message)
                summary["duplicate_warning_count"] += 1
                summary["needs_review_count"] += 1
                outcomes["needs_review"].append(
                    f"line {line_no}: duplicate mobile phone"
                )
                continue
            seen_phone_to_line[phone_e164] = line_no

            if phone_e164 in inactive_phones:
                row_active = False

            staged_rows.append(
                {
                    "line_no": str(line_no),
                    "first_name": first_name,
                    "last_name": last_name,
                    "display_name": f"{first_name} {last_name}",
                    "phone_e164": phone_e164,
                    "provider_driver_id": provider_driver_id,
                    "is_active": row_active,
                }
            )

        for staged in staged_rows:
            phone_e164 = str(staged["phone_e164"])
            display_name = str(staged["display_name"])
            existing = existing_by_phone.get(phone_e164)
            if existing is None:
                existing = Driver(
                    org_id=org_id,
                    phone_e164=phone_e164,
                    display_name=display_name,
                    is_active=bool(staged["is_active"]),
                )
                db.add(existing)
                db.flush()
                outcomes["imported"].append(phone_e164)
                existing_by_phone[phone_e164] = existing
            else:
                if existing.org_id != org_id:
                    message = (
                        f"{phone_e164}: already exists in another organization; skipped"
                    )
                    outcomes["errored"].append(message)
                    outcomes["duplicate_warning"].append(message)
                    outcomes["skipped"].append(message)
                    summary["duplicate_warning_count"] += 1
                    summary["needs_review_count"] += 1
                    outcomes["needs_review"].append(message)
                    warnings.append(f"Driver {message}.")
                    continue
                existing.display_name = display_name
                existing.is_active = bool(staged["is_active"])
                outcomes["updated"].append(phone_e164)

            if not bool(staged["is_active"]):
                summary["inactive_count"] += 1
                outcomes["skipped"].append(f"{phone_e164}: inactive")

            missing_reasons: list[str] = []
            if str(existing.driver_id) not in assigned_driver_ids:
                summary["missing_assignment_count"] += 1
                missing_reasons.append("assignment")
            if str(existing.driver_id).lower() not in provider_mapped_driver_ids:
                summary["missing_external_mapping_count"] += 1
                missing_reasons.append("external_mapping")

            if missing_reasons:
                summary["needs_review_count"] += 1
                details = ", ".join(missing_reasons)
                message = f"{phone_e164}: missing {details}"
                outcomes["missing_assignment_or_mapping"].append(message)
                outcomes["needs_review"].append(message)
                warnings.append(f"Driver {phone_e164} missing {details}.")

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
