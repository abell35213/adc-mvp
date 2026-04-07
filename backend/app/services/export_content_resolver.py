"""Resolve export package contents and canonical paths."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from app.domain.packet_profiles import get_default_packet_profile, get_packet_profile

@dataclass
class ResolvedExportContent:
    files: dict[str, bytes]
    file_manifest: list[dict[str, Any]]
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
    options: dict[str, Any] | None = None,
) -> ResolvedExportContent:
    files: dict[str, bytes] = {}
    warnings: list[dict[str, str]] = []
    missing_items: list[dict[str, str]] = []
    file_manifest: list[dict[str, Any]] = []
    options = dict(options or {})
    profile_id = str(options.get("profile_id") or options.get("profile") or get_default_packet_profile("court_defense").profile_id)
    profile = get_packet_profile(profile_id)
    include_media = bool(options.get("include_media", True))
    include_raw_telemetry = bool(options.get("include_raw_telemetry", True))
    include_driver_statement = bool(options.get("include_driver_statement", True))

    def _record_item(
        *,
        kind: str,
        item: str,
        path: str | None,
        classification: str,
        reason: str = "",
        byte_size: int | None = None,
    ) -> None:
        file_manifest.append(
            {
                "kind": kind,
                "item": item,
                "path": path,
                "classification": classification,
                "included": classification == "included",
                "reason": reason,
                "byte_size": byte_size if isinstance(byte_size, int) and byte_size >= 0 else None,
            }
        )

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
    _record_item(
        kind="incident_summary",
        item="01_Incident_Summary.json",
        path=f"{package_root}/01_Incident_Summary.json",
        classification="included",
    )

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
    inventory_headers = (
        ["artifact_type", "status", "s3_key", "byte_size"]
        if profile.inventory_mode == "condensed"
        else ["artifact_id", "artifact_type", "status", "s3_key", "sha256", "byte_size"]
    )
    if profile.inventory_mode == "condensed":
        inventory_rows = [[row[1], row[2], row[3], row[5]] for row in inventory_rows]
    files[f"{package_root}/02_Evidence_Inventory.csv"] = _csv_bytes(inventory_headers, inventory_rows)
    _record_item(
        kind="evidence_inventory",
        item="02_Evidence_Inventory.csv",
        path=f"{package_root}/02_Evidence_Inventory.csv",
        classification="included",
    )

    sorted_events = sorted(events, key=lambda e: str(e.occurred_at_utc))
    coc_rows = [
        [str(e.id), e.event_type, str(e.occurred_at_utc), e.actor_type, e.actor_id] for e in sorted_events
    ]
    files[f"{package_root}/03_Chain_of_Custody.csv"] = _csv_bytes(
        ["event_id", "event_type", "occurred_at_utc", "actor_type", "actor_id"],
        coc_rows,
    )
    _record_item(
        kind="chain_of_custody",
        item="03_Chain_of_Custody.csv",
        path=f"{package_root}/03_Chain_of_Custody.csv",
        classification="included",
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
    _record_item(
        kind="timeline",
        item="04_Timeline.csv",
        path=f"{package_root}/04_Timeline.csv",
        classification="included",
    )
    if profile.summary_style == "claim_focused":
        claim_bundle = {
            "profile_id": profile.profile_id,
            "bundle_kind": "claim_focused",
            "incident_id": incident_id,
            "export_id": export_id,
            "artifact_count": len(artifacts),
            "timeline_event_count": len(events),
        }
        files[f"{package_root}/04a_Claim_Focus_Bundle.json"] = json.dumps(
            claim_bundle,
            indent=2,
            default=str,
        ).encode()
        _record_item(
            kind="claim_bundle",
            item="04a_Claim_Focus_Bundle.json",
            path=f"{package_root}/04a_Claim_Focus_Bundle.json",
            classification="included",
        )

    statement_marker = "Driver statement unavailable at export generation time."
    if include_driver_statement:
        files[f"{package_root}/05_Driver_Statement.txt"] = statement_marker.encode()
        _record_item(
            kind="driver_statement",
            item="05_Driver_Statement.txt",
            path=f"{package_root}/05_Driver_Statement.txt",
            classification="unavailable",
            reason="driver_statement_not_captured",
        )
    else:
        _record_item(
            kind="driver_statement",
            item="05_Driver_Statement.txt",
            path=None,
            classification="excluded_by_option",
            reason="include_driver_statement=false",
        )

    for artifact in artifacts:
        filename = _artifact_filename(artifact.s3_key)
        target = _target_folder(artifact.artifact_type, filename)
        if target.startswith("media") and not include_media:
            _record_item(
                kind=artifact.artifact_type or "unknown",
                item=filename or str(artifact.artifact_id),
                path=None,
                classification="excluded_by_option",
                reason="include_media=false",
                byte_size=artifact.byte_size,
            )
            continue
        if target in {"gps", "eld", "safety", "vehicle"} and not include_raw_telemetry:
            _record_item(
                kind=artifact.artifact_type or "unknown",
                item=filename or str(artifact.artifact_id),
                path=None,
                classification="excluded_by_option",
                reason="include_raw_telemetry=false",
                byte_size=artifact.byte_size,
            )
            continue
        if artifact.status != "captured" or not artifact.s3_key or not filename:
            missing_items.append({"kind": artifact.artifact_type, "item": filename or str(artifact.artifact_id)})
            _record_item(
                kind=artifact.artifact_type or "unknown",
                item=filename or str(artifact.artifact_id),
                path=None,
                classification="unavailable",
                reason=f"artifact_status={artifact.status}",
                byte_size=artifact.byte_size,
            )
            continue
        path = str(PurePosixPath(package_root) / target / filename)
        try:
            data = s3.download(artifact.s3_key)
        except Exception as exc:
            warnings.append({"kind": "artifact_missing_from_s3", "item": artifact.s3_key, "reason": str(exc)})
            missing_items.append({"kind": artifact.artifact_type, "item": filename})
            _record_item(
                kind=artifact.artifact_type or "unknown",
                item=filename,
                path=path,
                classification="failed_to_retrieve",
                reason=str(exc),
                byte_size=artifact.byte_size,
            )
            continue
        files[path] = data
        _record_item(
            kind=artifact.artifact_type or "unknown",
            item=filename,
            path=path,
            classification="included",
            byte_size=len(data),
        )

        if artifact.artifact_type in {"driver_statement", "driver_narrative", "driver_report"}:
            try:
                files[f"{package_root}/05_Driver_Statement.txt"] = data.decode(errors="replace").encode()
                _record_item(
                    kind="driver_statement",
                    item="05_Driver_Statement.txt",
                    path=f"{package_root}/05_Driver_Statement.txt",
                    classification="included",
                )
            except Exception:
                pass

    readme = """ADC Export Package\n\nVerification:\n1. cd into the package root folder.\n2. Run: sha256sum -c integrity/checksums.sha256\n\nInterpretation guidance:\n- 01_Incident_Summary.json: high-level package metadata.\n- 02_Evidence_Inventory.csv: inventory of known artifacts.\n- 03_Chain_of_Custody.csv: event custody log.\n- 04_Timeline.csv: chronological timeline of recorded events.\n- 05_Driver_Statement.txt: driver narrative or unavailable marker.\n"""
    files[f"{package_root}/readme/00_README.txt"] = readme.encode()
    _record_item(
        kind="readme",
        item="00_README.txt",
        path=f"{package_root}/readme/00_README.txt",
        classification="included",
    )

    return ResolvedExportContent(
        files=files,
        file_manifest=file_manifest,
        missing_items=missing_items,
        warnings=warnings,
    )
