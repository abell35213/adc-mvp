"""Coordinator service for building ADC export packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.export_content_resolver import resolve_export_content
from app.services.export_manifest import build_export_manifest
from app.services.export_pdf_service import (
    build_export_pdf_context,
    render_cover_summary_pdf,
)
from app.services.export_zip_service import (
    build_checksums_sha256,
    build_export_zip,
    build_package_integrity,
    hash_bytes,
    to_json_bytes,
)


@dataclass
class ExportBuildResult:
    zip_bytes: bytes
    package_sha256: str
    byte_size: int
    included_files: list[str]
    file_manifest: list[dict]
    missing_items: list[dict[str, str]]
    warnings: list[dict[str, str]]


def build_export_package(
    *,
    incident_id: str,
    export_id: str,
    artifacts: list,
    events: list,
    s3,
    options: dict,
    incident=None,
    export=None,
) -> ExportBuildResult:
    package_root = f"ADC_Export_{incident_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    resolved = resolve_export_content(
        incident_id=incident_id,
        export_id=export_id,
        artifacts=artifacts,
        events=events,
        s3=s3,
        package_root=package_root,
        options=options,
    )

    files = dict(resolved.files)
    file_manifest = list(resolved.file_manifest)

    pdf_context = build_export_pdf_context(
        package_root=package_root,
        incident=incident,
        export=export,
        artifacts=artifacts,
        events=events,
        warnings=resolved.warnings,
        missing_items=resolved.missing_items,
    )
    files[f"{package_root}/00_Cover_Summary.pdf"] = render_cover_summary_pdf(pdf_context)
    file_manifest.append(
        {
            "kind": "summary_pdf",
            "item": "00_Cover_Summary.pdf",
            "path": f"{package_root}/00_Cover_Summary.pdf",
            "classification": "included",
            "included": True,
            "reason": "",
            "byte_size": None,
        }
    )

    checksums = build_checksums_sha256(files, package_root)
    files[f"{package_root}/integrity/checksums.sha256"] = checksums
    file_manifest.append(
        {
            "kind": "integrity",
            "item": "checksums.sha256",
            "path": f"{package_root}/integrity/checksums.sha256",
            "classification": "included",
            "included": True,
            "reason": "",
            "byte_size": len(checksums),
        }
    )

    manifest = build_export_manifest(
        options=options,
        included_files=list(files.keys()),
        file_manifest=file_manifest,
        missing_items=resolved.missing_items,
        status_metadata={
            "warnings_count": len(resolved.warnings),
            "missing_items_count": len(resolved.missing_items),
            "artifact_count": len(artifacts),
            "timeline_event_count": len(events),
        },
    )
    files[f"{package_root}/metadata/export_manifest.json"] = to_json_bytes(manifest)
    file_manifest.append(
        {
            "kind": "manifest",
            "item": "export_manifest.json",
            "path": f"{package_root}/metadata/export_manifest.json",
            "classification": "included",
            "included": True,
            "reason": "",
            "byte_size": None,
        }
    )

    zip_bytes = build_export_zip(files)
    package_sha256 = hash_bytes(zip_bytes)
    integrity = build_package_integrity(package_sha256=package_sha256, file_count=len(files))
    files[f"{package_root}/metadata/package_integrity.json"] = to_json_bytes(integrity)
    file_manifest.append(
        {
            "kind": "package_integrity",
            "item": "package_integrity.json",
            "path": f"{package_root}/metadata/package_integrity.json",
            "classification": "included",
            "included": True,
            "reason": "",
            "byte_size": None,
        }
    )

    zip_bytes = build_export_zip(files)
    package_sha256 = hash_bytes(zip_bytes)

    return ExportBuildResult(
        zip_bytes=zip_bytes,
        package_sha256=package_sha256,
        byte_size=len(zip_bytes),
        included_files=sorted(files.keys()),
        file_manifest=file_manifest,
        missing_items=resolved.missing_items,
        warnings=resolved.warnings,
    )
