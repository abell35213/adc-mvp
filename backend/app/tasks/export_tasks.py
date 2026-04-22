"""Export generation tasks."""

import csv
import hashlib
import io
import logging
import re
import uuid as _uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.metrics import increment
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
ALLOWED_ARTIFACT_EXTENSIONS = {"json", "csv", "mp4"}
SAFE_ARTIFACT_TYPE_RE = re.compile(r"[^A-Za-z0-9_-]+")
README_TEMPLATE = """ADC Court Evidence Package

Incident ID: {incident_id}
Export ID: {export_id}
Capture window (UTC, earliest start to latest end): {capture_start} to {capture_end}

Hashes:
SHA-256 hashes are computed from the raw bytes of each artifact
at capture time and recorded in integrity_appendix.csv.

Verification:
1. Compute the SHA-256 hash of a file (e.g., `sha256sum <file>`).
2. Compare the result with integrity_appendix.csv.
3. Matching hashes confirm the file integrity.
"""


@dataclass
class ExportRuntimeContext:
    db: Any
    incident_uuid: _uuid.UUID
    export_uuid: _uuid.UUID
    incident_id: str
    export_id: str
    workflow_key: str
    org_id: str
    settings: Any
    system_event_type: Any
    s3_key_builder: Any
    s3: Any
    export_row: Any
    incident_row: Any
    warnings: list[dict[str, str]]
    missing_items: list[dict[str, str]]
    artifacts: list[Any]
    events: list[Any]
    exportable_artifacts: list[tuple[Any, str]]
    inventory_csv_bytes: bytes
    coc_csv_bytes: bytes
    appendix_csv_bytes: bytes
    readme_content: str
    zip_bytes: bytes
    zip_key: str | None


def _hash_bytes(data: bytes) -> str:
    """Return hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _idempotency_key(*parts: str | None) -> str:
    """Return a deterministic idempotency key from stable task inputs."""
    normalized = [p or "none" for p in parts]
    return _hash_bytes("|".join(normalized).encode())


def _get_db():
    """Return a new database session (non-generator helper for tasks)."""
    from app.db.session import SessionLocal

    return SessionLocal()


def _get_org_id(db, incident_id):
    """Return the org_id string for an incident."""
    from app.db.repo.incidents import get_incident

    incident = get_incident(db, incident_id)
    if incident is None or incident.org_id is None:
        raise ValueError(f"Incident {incident_id} missing org_id")
    return str(incident.org_id)


def _emit(db, incident_id, event_type, payload=None):
    """Append an event to the append-only log."""
    from app.db.repo.events import create_event

    return create_event(
        db,
        incident_id=incident_id,
        event_type=event_type,
        actor_type="system",
        actor_id="celery",
        payload=payload,
    )


def _event_exists(db, incident_id, event_type: str, idempotency_key: str) -> bool:
    from app.db.repo.events import get_events_by_incident

    events = get_events_by_incident(db, incident_id)
    return any(
        ev.event_type == event_type
        and isinstance(ev.payload, dict)
        and ev.payload.get("idempotency_key") == idempotency_key
        for ev in events
    )


def _emit_once(db, incident_id, event_type, idempotency_key: str, payload=None):
    full_payload = {"idempotency_key": idempotency_key, **(payload or {})}
    if _event_exists(db, incident_id, event_type, idempotency_key):
        return None
    return _emit(db, incident_id, event_type, full_payload)


def _artifact_filename(s3_key):
    if not s3_key:
        return ""
    return s3_key.rsplit("/", 1)[-1]


def _artifact_extension(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _safe_artifact_type(artifact_type):
    if not artifact_type:
        return "unknown"
    sanitized = SAFE_ARTIFACT_TYPE_RE.sub("_", artifact_type).strip("_-")
    # Fall back to a stable label if sanitization leaves an empty string.
    return sanitized or "unknown"


def _set_progress_stage(ctx: ExportRuntimeContext, stage: str, status: str = "processing"):
    from app.db.repo.exports import update_export

    update_export(ctx.db, export_id=ctx.export_uuid, status=status, progress_stage=stage)


def _emit_stage(ctx: ExportRuntimeContext, phase: str, stage: str):
    _emit(
        ctx.db,
        ctx.incident_uuid,
        "export_stage",
        {
            "idempotency_key": ctx.workflow_key,
            "export_id": ctx.export_id,
            "stage": stage,
            "phase": phase,
        },
    )


def _export_event_payload(
    ctx: ExportRuntimeContext,
    status: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "idempotency_key": ctx.workflow_key,
        "export_id": ctx.export_id,
        "incident_id": ctx.incident_id,
        "export_type": ctx.export_row.export_type,
        "status": status,
        "actor": {"type": "system", "id": "celery"},
    }
    if extra:
        payload.update(extra)
    return payload


def _persist_warnings(ctx: ExportRuntimeContext):
    from app.db.repo.exports import update_export

    options = dict(ctx.export_row.options_json or {})
    options["warnings"] = ctx.warnings
    options["missing_items"] = ctx.missing_items
    update_export(ctx.db, export_id=ctx.export_uuid, options_json=options)
    ctx.export_row.options_json = options


def _load_context(ctx: ExportRuntimeContext):
    from app.db.repo.artifacts import get_artifacts_by_incident
    from app.db.repo.events import get_events_by_incident
    from app.audit.emitter import emit_audit_event

    ctx.artifacts = get_artifacts_by_incident(ctx.db, ctx.incident_uuid)
    ctx.events = get_events_by_incident(ctx.db, ctx.incident_uuid)
    for artifact in ctx.artifacts:
        emit_audit_event(
            ctx.db,
            org_id=_uuid.UUID(ctx.org_id),
            actor_type="system",
            actor_id="celery",
            action="artifact.retrieve",
            event_type="artifact_retrieved",
            outcome="success",
            incident_id=ctx.incident_uuid,
            export_id=ctx.export_uuid,
            artifact_id=artifact.artifact_id,
            metadata={"artifact_type": artifact.artifact_type, "status": artifact.status},
        )

    exportable_artifacts: list[tuple[Any, str]] = []
    for artifact in ctx.artifacts:
        filename = _artifact_filename(artifact.s3_key)
        extension = _artifact_extension(filename)
        if (
            artifact.status == "captured"
            and artifact.s3_key
            and extension in ALLOWED_ARTIFACT_EXTENSIONS
        ):
            exportable_artifacts.append((artifact, filename))
        elif artifact.status == "captured" and artifact.s3_key:
            ctx.warnings.append(
                {
                    "kind": "artifact_skipped_extension",
                    "item": artifact.s3_key,
                    "reason": "extension_not_allowed",
                }
            )
            ctx.missing_items.append(
                {"kind": _safe_artifact_type(artifact.artifact_type), "item": filename}
            )
    ctx.exportable_artifacts = exportable_artifacts


def _build_machine_readable_docs(ctx: ExportRuntimeContext):
    appendix_buf = io.StringIO()
    appendix_writer = csv.writer(appendix_buf)
    appendix_writer.writerow(
        ["artifact_id", "artifact_type", "file_name", "sha256", "byte_size", "included", "note"]
    )
    for artifact, filename in ctx.exportable_artifacts:
        appendix_writer.writerow(
            [
                str(artifact.artifact_id),
                artifact.artifact_type,
                filename,
                artifact.sha256 or "",
                artifact.byte_size or "",
                "true",
                "",
            ]
        )
    for warning in ctx.warnings:
        if warning.get("kind") != "artifact_missing_from_s3":
            continue
        appendix_writer.writerow(["", "optional", warning.get("item", ""), "", "", "false", warning.get("reason", "")])
    ctx.appendix_csv_bytes = appendix_buf.getvalue().encode()


def _render_human_readable_docs(ctx: ExportRuntimeContext):
    inv_buf = io.StringIO()
    inv_writer = csv.writer(inv_buf)
    inv_writer.writerow(["artifact_id", "artifact_type", "status", "s3_key", "sha256", "byte_size"])
    for artifact in ctx.artifacts:
        inv_writer.writerow(
            [
                str(artifact.artifact_id),
                artifact.artifact_type,
                artifact.status,
                artifact.s3_key or "",
                artifact.sha256 or "",
                artifact.byte_size or "",
            ]
        )
    ctx.inventory_csv_bytes = inv_buf.getvalue().encode()

    sorted_events = sorted(ctx.events, key=lambda event: str(event.occurred_at_utc))
    coc_buf = io.StringIO()
    coc_writer = csv.writer(coc_buf)
    coc_writer.writerow(["event_id", "event_type", "occurred_at_utc", "actor_type", "actor_id"])
    for event in sorted_events:
        coc_writer.writerow([str(event.id), event.event_type, str(event.occurred_at_utc), event.actor_type, event.actor_id])
    ctx.coc_csv_bytes = coc_buf.getvalue().encode()

    capture_start = None
    capture_end = None
    for artifact, _ in ctx.exportable_artifacts:
        if artifact.capture_window_start_utc is not None and (
            capture_start is None or artifact.capture_window_start_utc < capture_start
        ):
            capture_start = artifact.capture_window_start_utc
        if artifact.capture_window_end_utc is not None and (
            capture_end is None or artifact.capture_window_end_utc > capture_end
        ):
            capture_end = artifact.capture_window_end_utc
    ctx.readme_content = README_TEMPLATE.format(
        incident_id=ctx.incident_id,
        export_id=ctx.export_id,
        capture_start=capture_start.isoformat() if capture_start else "Unavailable",
        capture_end=capture_end.isoformat() if capture_end else "Unavailable",
    )


def _assemble_zip(ctx: ExportRuntimeContext):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        package_root = "ADC_Court_Package"
        zf.writestr(f"{package_root}/00_README.txt", ctx.readme_content)
        zf.writestr(f"{package_root}/02_Evidence_Inventory.csv", ctx.inventory_csv_bytes)
        zf.writestr(f"{package_root}/03_Chain_of_Custody.csv", ctx.coc_csv_bytes)
        zf.writestr(f"{package_root}/integrity_appendix.csv", ctx.appendix_csv_bytes)

        for artifact, filename in ctx.exportable_artifacts:
            safe_artifact_type = _safe_artifact_type(artifact.artifact_type)
            try:
                artifact_data = ctx.s3.download(artifact.s3_key)
                zf.writestr(f"{package_root}/artifacts/{safe_artifact_type}/{filename}", artifact_data)
            except Exception as exc:
                logger.warning("Could not include artifact %s in export", artifact.s3_key, exc_info=True)
                ctx.warnings.append(
                    {"kind": "artifact_missing_from_s3", "item": artifact.s3_key or filename, "reason": str(exc)}
                )
                ctx.missing_items.append({"kind": safe_artifact_type, "item": filename})
    ctx.zip_bytes = zip_buffer.getvalue()
    if not ctx.zip_bytes:
        raise RuntimeError("ZIP finalization failed: empty package")


def _generate_integrity(ctx: ExportRuntimeContext):
    if not ctx.appendix_csv_bytes:
        raise RuntimeError("Manifest generation failed: integrity appendix missing")
    if not ctx.zip_bytes:
        raise RuntimeError("ZIP finalization failed: zip bytes missing")


def _upload_and_finalize(ctx: ExportRuntimeContext):
    from app.db.repo.exports import update_export

    if ctx.zip_bytes is None:
        raise RuntimeError("ZIP finalization failed: missing bytes before upload")
    ctx.zip_key = ctx.s3_key_builder.export_key(
        org_id=ctx.org_id,
        incident_id=ctx.incident_id,
        export_id=ctx.export_id,
    )
    if not ctx.zip_key:
        raise RuntimeError("Manifest generation failed: export key missing")
    ctx.s3.put_bytes(ctx.zip_key, ctx.zip_bytes)
    update_export(
        ctx.db,
        export_id=ctx.export_uuid,
        status="ready",
        progress_stage="ready_for_download",
        s3_bucket=ctx.settings.S3_BUCKET,
        s3_key=ctx.zip_key,
        package_sha256=_hash_bytes(ctx.zip_bytes),
        byte_size=len(ctx.zip_bytes),
        artifact_count=len(ctx.exportable_artifacts),
        timeline_event_count=len(ctx.events),
    )


def _sync_incident_case_status_after_export(ctx: ExportRuntimeContext):
    from app.db.repo.events import create_event

    incident_model = type(ctx.incident_row) if ctx.incident_row is not None else None
    if incident_model is None:
        return
    incident_row = ctx.db.get(incident_model, ctx.incident_uuid, populate_existing=True)
    if incident_row is None:
        return
    if str(incident_row.case_status) != "ready_for_export":
        return

    ctx.incident_row = incident_row
    incident_row.case_status = "exported"
    incident_row.readiness_state = "exported"
    db_now = datetime.now(timezone.utc)
    incident_row.last_activity_at_utc = db_now
    ctx.db.flush()
    create_event(
        ctx.db,
        incident_id=ctx.incident_uuid,
        event_type=ctx.system_event_type.INCIDENT_STATUS_CHANGED,
        actor_type="system",
        actor_id="celery",
        payload={
            "from_case_status": "ready_for_export",
            "to_case_status": "exported",
            "transition_reason": "export_completed",
            "transitioned_at_utc": db_now.isoformat(),
            "export_id": ctx.export_id,
            "actor": {"type": "system", "id": "celery"},
        },
    )


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=2,
    soft_time_limit=300,
    time_limit=360,
)
def build_export(
    self,
    incident_id: str,
    export_id: str,
    attempt_context: dict | None = None,
):
    """Generate an export package for an incident.

    Steps:
    1. Emit EXPORT_REQUESTED (if not already emitted)
    2. Read artifacts and events for the incident
    3. Generate Evidence Inventory CSV
    4. Generate Chain-of-Custody CSV (derived from events)
    5. Generate Integrity Appendix CSV and README
    6. Bundle artifact files into a ZIP
    7. Upload ZIP to S3
    8. Update export row to ready
    9. Emit EXPORT_GENERATED
    """
    increment("exports.build.attempts")
    logger.info(
        "Starting export build task",
        extra={"incident_id": incident_id, "export_id": export_id, "attempt_context": attempt_context or {}},
    )
    from app.core.config import settings
    from app.audit.emitter import emit_audit_event
    from app.db.repo.exports import get_export, update_export
    from app.db.repo.incidents import get_incident
    from app.domain.system_event_types import SystemEventType
    from app.services import s3_key_builder
    from app.services.export_builder import build_export_package
    from app.services.vault_s3 import VaultS3

    inc_uuid = _uuid.UUID(incident_id)
    exp_uuid = _uuid.UUID(export_id)
    workflow_key = _idempotency_key("export", incident_id, export_id)
    db = _get_db()
    inc_uuid = _uuid.UUID(incident_id)
    ctx = None

    try:
        org_id = _get_org_id(db, inc_uuid)
        export_row = get_export(db, exp_uuid)
        if export_row is None:
            raise ValueError(f"Export {export_id} not found")
        incident_row = get_incident(db, inc_uuid)

        attempt_id = str((attempt_context or {}).get("attempt_id") or workflow_key)
        if export_row.status == "ready" and export_row.s3_key:
            return {
                "export_id": export_id,
                "incident_id": incident_id,
                "status": "ready",
                "idempotency_key": workflow_key,
                "s3_key": export_row.s3_key,
                "duplicate": True,
            }

        if export_row.status == "processing":
            existing_attempt = (export_row.options_json or {}).get("attempt_id")
            if existing_attempt and existing_attempt != attempt_id:
                return {
                    "export_id": export_id,
                    "incident_id": incident_id,
                    "status": export_row.status,
                    "idempotency_key": workflow_key,
                    "duplicate": True,
                }

        options = dict(export_row.options_json or {})
        if export_row.profile_id:
            options["profile_id"] = export_row.profile_id
        options["attempt_id"] = attempt_id
        update_export(
            db,
            export_id=exp_uuid,
            status="processing",
            progress_stage="gathering_incident_data",
            error_message=None,
            options_json=options,
        )
        export_row.options_json = options
        emit_audit_event(
            db,
            org_id=_uuid.UUID(org_id),
            actor_type="system",
            actor_id="celery",
            action="export.request",
            event_type="export_requested",
            outcome="success",
            incident_id=inc_uuid,
            export_id=exp_uuid,
            metadata={"trigger": (attempt_context or {}).get("trigger", "worker")},
        )
        ctx = ExportRuntimeContext(
            db=db,
            incident_uuid=inc_uuid,
            export_uuid=exp_uuid,
            incident_id=incident_id,
            export_id=export_id,
            workflow_key=workflow_key,
            org_id=org_id,
            settings=settings,
            system_event_type=SystemEventType,
            s3_key_builder=s3_key_builder,
            s3=VaultS3(bucket=settings.S3_BUCKET, region=settings.AWS_REGION),
            export_row=export_row,
            incident_row=incident_row,
            warnings=[],
            missing_items=[],
            artifacts=[],
            events=[],
            exportable_artifacts=[],
            inventory_csv_bytes=b"",
            coc_csv_bytes=b"",
            appendix_csv_bytes=b"",
            readme_content="",
            zip_bytes=b"",
            zip_key=None,
        )
        # 1. Emit EXPORT_REQUESTED if not already recorded
        from app.db.repo.events import get_events_by_incident

        existing_events = get_events_by_incident(db, inc_uuid)
        already_requested = any(
            e.event_type == SystemEventType.EXPORT_REQUESTED
            and e.payload
            and e.payload.get("export_id") == export_id
            for e in existing_events
        )
        if not already_requested:
            _emit_once(
                db,
                inc_uuid,
                SystemEventType.EXPORT_REQUESTED,
                workflow_key,
                _export_event_payload(
                    ctx,
                    "requested",
                ),
            )
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EXPORT_PROCESSING_STARTED,
            workflow_key,
            _export_event_payload(ctx, "processing"),
        )
        # 2. Load context
        _emit_stage(ctx, "before", "gathering_incident_data")
        _set_progress_stage(ctx, "gathering_incident_data")
        _load_context(ctx)
        _persist_warnings(ctx)
        _emit_stage(ctx, "after", "gathering_incident_data")

        # 3-6. Build export content, manifest, and ZIP package
        _emit_stage(ctx, "before", "assembling_documents")
        _set_progress_stage(ctx, "assembling_documents")
        build_result = build_export_package(
            incident_id=ctx.incident_id,
            export_id=ctx.export_id,
            artifacts=ctx.artifacts,
            events=ctx.events,
            s3=ctx.s3,
            options=dict(ctx.export_row.options_json or {}),
            incident=ctx.incident_row,
            export=ctx.export_row,
        )
        ctx.zip_bytes = build_result.zip_bytes
        ctx.warnings.extend(build_result.warnings)
        ctx.missing_items.extend(build_result.missing_items)
        _persist_warnings(ctx)
        options = dict(ctx.export_row.options_json or {})
        options["file_manifest"] = build_result.file_manifest
        update_export(ctx.db, export_id=ctx.export_uuid, options_json=options)
        ctx.export_row.options_json = options
        _emit_stage(ctx, "after", "assembling_documents")
        _emit(
            ctx.db,
            ctx.incident_uuid,
            SystemEventType.EXPORT_SECTION_GENERATED,
            _export_event_payload(
                ctx,
                "processing",
                {
                    "section": "document_bundle",
                    "file_manifest_count": len(build_result.file_manifest),
                },
            ),
        )

        _emit_stage(ctx, "before", "packaging_evidence")
        _set_progress_stage(ctx, "packaging_evidence")
        _emit_stage(ctx, "after", "packaging_evidence")

        # 7. Upload + finalize
        _emit_stage(ctx, "before", "uploading_export")
        _set_progress_stage(ctx, "uploading_export")
        _upload_and_finalize(ctx)
        update_export(
            ctx.db,
            export_id=ctx.export_uuid,
            package_sha256=build_result.package_sha256,
            byte_size=build_result.byte_size,
        )
        _sync_incident_case_status_after_export(ctx)
        _emit_stage(ctx, "after", "uploading_export")
        _emit(
            ctx.db,
            ctx.incident_uuid,
            SystemEventType.EXPORT_PACKAGE_UPLOADED,
            _export_event_payload(
                ctx,
                "ready",
                {
                    "package": {
                        "s3_bucket": ctx.settings.S3_BUCKET,
                        "s3_key": ctx.zip_key,
                        "sha256": build_result.package_sha256,
                        "byte_size": build_result.byte_size,
                    }
                },
            ),
        )

        # 8. Emit EXPORT_GENERATED
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EXPORT_GENERATED,
            workflow_key,
            _export_event_payload(
                ctx,
                "ready",
                {
                    "package": {
                        "s3_bucket": ctx.settings.S3_BUCKET,
                        "s3_key": ctx.zip_key,
                        "sha256": _hash_bytes(ctx.zip_bytes),
                        "byte_size": len(ctx.zip_bytes),
                    },
                    "sha256": _hash_bytes(ctx.zip_bytes),
                    "byte_size": len(ctx.zip_bytes),
                    "warnings_count": len(ctx.warnings),
                    "missing_items_count": len(ctx.missing_items),
                },
            ),
        )

        emit_audit_event(
            db,
            org_id=_uuid.UUID(org_id),
            actor_type="system",
            actor_id="celery",
            action="export.generate",
            event_type="export_download_ready",
            outcome="success",
            incident_id=inc_uuid,
            export_id=exp_uuid,
            metadata={"warnings_count": len(ctx.warnings), "missing_items_count": len(ctx.missing_items)},
        )
        return {
            "export_id": export_id,
            "incident_id": incident_id,
            "status": "ready",
            "idempotency_key": workflow_key,
            "warnings": ctx.warnings,
            "missing_items": ctx.missing_items,
            "duplicate": False,
        }

    except Exception as exc:
        from app.db.repo.exports import update_export

        logger.exception("Export %s failed for incident %s", export_id, incident_id)
        if ctx is not None:
            _persist_warnings(ctx)
        update_export(
            db,
            export_id=exp_uuid,
            status="failed",
            error_message=str(exc)[:4000],
        )
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EXPORT_FAILED,
            workflow_key,
            {
                "idempotency_key": workflow_key,
                "export_id": export_id,
                "incident_id": incident_id,
                "status": "failed",
                "actor": {"type": "system", "id": "celery"},
                "error_message": str(exc),
            },
        )
        try:
            emit_audit_event(
                db,
                org_id=_uuid.UUID(_get_org_id(db, inc_uuid)),
                actor_type="system",
                actor_id="celery",
                action="export.generate",
                event_type="export_generation_failed",
                outcome="failure",
                incident_id=inc_uuid,
                export_id=exp_uuid,
                metadata={"error": str(exc), "should_log": True},
            )
        except Exception:
            logger.exception("Failed to append audit event for export failure")
        raise
    finally:
        db.close()


# Backward-compatible alias
generate_export = build_export
