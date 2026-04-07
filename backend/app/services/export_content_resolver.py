"""Resolve export package contents and canonical paths."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any


@dataclass
class ResolvedExportContent:
    files: dict[str, bytes]
    missing_items: list[dict[str, str]]
    warnings: list[dict[str, str]]


def _csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode()


def _artifact_filename(s3_key: str | None) -> str:
    if not s3_key:
        return ""
    return s3_key.rsplit("/", 1)[-1]


def _target_folder(artifact_type: str, filename: str) -> str:
    if artifact_type == "gps_trail":
        return "gps"
    if artifact_type == "eld_log":
        return "eld"
    if artifact_type == "safety_event":
        return "safety"
    if artifact_type == "vehicle_state":
        return "vehicle"
    lower_type = (artifact_type or "").lower()
    lower_name = (filename or "").lower()
    if "dashcam" in lower_type or lower_name.endswith((".mp4", ".jpg", ".jpeg", ".png")):
        return "media"
    return "media/other"


def resolve_export_content(
    *,
    incident_id: str,
    export_id: str,
    artifacts: list[Any],
    events: list[Any],
    s3: Any,
    package_root: str,
) -> ResolvedExportContent:
    files: dict[str, bytes] = {}
    warnings: list[dict[str, str]] = []
    missing_items: list[dict[str, str]] = []

    incident_summary = {
        "incident_id": incident_id,
        "export_id": export_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_count": len(artifacts),
        "timeline_event_count": len(events),
    }
    files[f"{package_root}/01_Incident_Summary.json"] = json.dumps(
        incident_summary,
        indent=2,
        default=str,
    ).encode()

    inventory_rows = [
        [
            str(a.artifact_id),
            a.artifact_type,
            a.status,
            a.s3_key or "",
            a.sha256 or "",
            a.byte_size or "",
        ]
        for a in artifacts
    ]
    files[f"{package_root}/02_Evidence_Inventory.csv"] = _csv_bytes(
        ["artifact_id", "artifact_type", "status", "s3_key", "sha256", "byte_size"],
        inventory_rows,
    )

    sorted_events = sorted(events, key=lambda e: str(e.occurred_at_utc))
    coc_rows = [
        [str(e.id), e.event_type, str(e.occurred_at_utc), e.actor_type, e.actor_id] for e in sorted_events
    ]
    files[f"{package_root}/03_Chain_of_Custody.csv"] = _csv_bytes(
        ["event_id", "event_type", "occurred_at_utc", "actor_type", "actor_id"],
        coc_rows,
    )

    timeline_rows = [
        [
            str(e.occurred_at_utc),
            e.event_type,
            e.actor_type,
            e.actor_id,
            json.dumps(e.payload or {}, default=str),
        ]
        for e in sorted_events
    ]
    files[f"{package_root}/04_Timeline.csv"] = _csv_bytes(
        ["occurred_at_utc", "event_type", "actor_type", "actor_id", "payload_json"],
        timeline_rows,
    )

    statement_marker = "Driver statement unavailable at export generation time."
    files[f"{package_root}/05_Driver_Statement.txt"] = statement_marker.encode()

    for artifact in artifacts:
        filename = _artifact_filename(artifact.s3_key)
        if artifact.status != "captured" or not artifact.s3_key or not filename:
            missing_items.append({"kind": artifact.artifact_type, "item": filename or str(artifact.artifact_id)})
            continue
        target = _target_folder(artifact.artifact_type, filename)
        path = str(PurePosixPath(package_root) / target / filename)
        try:
            data = s3.download(artifact.s3_key)
        except Exception as exc:
            warnings.append({"kind": "artifact_missing_from_s3", "item": artifact.s3_key, "reason": str(exc)})
            missing_items.append({"kind": artifact.artifact_type, "item": filename})
            continue
        files[path] = data

        if artifact.artifact_type in {"driver_statement", "driver_narrative", "driver_report"}:
            try:
                files[f"{package_root}/05_Driver_Statement.txt"] = data.decode(errors="replace").encode()
            except Exception:
                pass

    readme = """ADC Export Package\n\nVerification:\n1. cd into the package root folder.\n2. Run: sha256sum -c integrity/checksums.sha256\n\nInterpretation guidance:\n- 01_Incident_Summary.json: high-level package metadata.\n- 02_Evidence_Inventory.csv: inventory of known artifacts.\n- 03_Chain_of_Custody.csv: event custody log.\n- 04_Timeline.csv: chronological timeline of recorded events.\n- 05_Driver_Statement.txt: driver narrative or unavailable marker.\n"""
    files[f"{package_root}/readme/00_README.txt"] = readme.encode()

    return ResolvedExportContent(files=files, missing_items=missing_items, warnings=warnings)
