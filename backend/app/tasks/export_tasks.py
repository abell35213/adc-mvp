"""Export generation tasks."""

import csv
import hashlib
import io
import logging
import re
import uuid as _uuid
import zipfile

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
ALLOWED_ARTIFACT_EXTENSIONS = {"json", "csv", "mp4"}
SAFE_ARTIFACT_TYPE_RE = re.compile(r"[^A-Za-z0-9_-]+")
README_TEMPLATE = "\n".join([
    "ADC Court Evidence Package",
    "",
    "Incident ID: {incident_id}",
    "Export ID: {export_id}",
    "Capture window (UTC, earliest start to latest end): "
    "{capture_start} to {capture_end}",
    "",
    "Hashes:",
    "SHA-256 hashes are computed from the raw bytes of each artifact",
    "at capture time and recorded in integrity_appendix.csv.",
    "",
    "Verification:",
    "1. Compute the SHA-256 hash of a file (e.g., `sha256sum <file>`).",
    "2. Compare the result with integrity_appendix.csv.",
    "3. Matching hashes confirm the file integrity.",
])


def _hash_bytes(data: bytes) -> str:
    """Return hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _get_db():
    """Return a new database session (non-generator helper for tasks)."""
    from app.db.session import SessionLocal

    return SessionLocal()


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
    return sanitized or "unknown"


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=2,
    soft_time_limit=300,
    time_limit=360,
)
def build_export(self, incident_id: str, export_id: str):
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
    from app.core.config import settings
    from app.db.repo.artifacts import get_artifacts_by_incident
    from app.db.repo.events import get_events_by_incident
    from app.db.repo.exports import update_export
    from app.domain.system_event_types import SystemEventType
    from app.services import s3_key_builder
    from app.services.vault_s3 import VaultS3

    inc_uuid = _uuid.UUID(incident_id)
    exp_uuid = _uuid.UUID(export_id)
    db = _get_db()

    try:
        # 1. Emit EXPORT_REQUESTED if not already recorded
        existing_events = get_events_by_incident(db, inc_uuid)
        already_requested = any(
            e.event_type == SystemEventType.EXPORT_REQUESTED
            and e.payload
            and e.payload.get("export_id") == export_id
            for e in existing_events
        )
        if not already_requested:
            _emit(db, inc_uuid, SystemEventType.EXPORT_REQUESTED, {
                "export_id": export_id,
            })

        # 2. Read artifacts and events
        artifacts = get_artifacts_by_incident(db, inc_uuid)
        events = get_events_by_incident(db, inc_uuid)

        s3 = VaultS3(bucket=settings.S3_BUCKET, region=settings.AWS_REGION)

        exportable_artifacts = []
        for artifact in artifacts:
            filename = _artifact_filename(artifact.s3_key)
            extension = _artifact_extension(filename)

            if (
                artifact.status == "captured"
                and artifact.s3_key
                and extension in ALLOWED_ARTIFACT_EXTENSIONS
            ):
                exportable_artifacts.append((artifact, filename))

        # 3. Generate Evidence Inventory CSV
        inv_buf = io.StringIO()
        inv_writer = csv.writer(inv_buf)
        inv_writer.writerow([
            "artifact_id", "artifact_type", "status", "s3_key",
            "sha256", "byte_size",
        ])
        for a in artifacts:
            inv_writer.writerow([
                str(a.artifact_id), a.artifact_type, a.status,
                a.s3_key or "", a.sha256 or "", a.byte_size or "",
            ])
        inventory_csv_bytes = inv_buf.getvalue().encode()

        # 4. Generate Chain-of-Custody CSV (derived from events timeline)
        sorted_events = sorted(events, key=lambda e: str(e.occurred_at_utc))

        coc_buf = io.StringIO()
        coc_writer = csv.writer(coc_buf)
        coc_writer.writerow([
            "event_id", "event_type", "occurred_at_utc",
            "actor_type", "actor_id",
        ])
        for ev in sorted_events:
            coc_writer.writerow([
                str(ev.id), ev.event_type,
                str(ev.occurred_at_utc),
                ev.actor_type, ev.actor_id,
            ])
        coc_csv_bytes = coc_buf.getvalue().encode()

        # 5. Generate Integrity Appendix CSV + README
        appendix_buf = io.StringIO()
        appendix_writer = csv.writer(appendix_buf)
        appendix_writer.writerow([
            "artifact_id", "artifact_type", "file_name", "sha256", "byte_size",
        ])
        for artifact, filename in exportable_artifacts:
            appendix_writer.writerow([
                str(artifact.artifact_id),
                artifact.artifact_type,
                filename,
                artifact.sha256 or "",
                artifact.byte_size or "",
            ])
        appendix_csv_bytes = appendix_buf.getvalue().encode()

        capture_starts = []
        capture_ends = []
        for artifact, _ in exportable_artifacts:
            if artifact.capture_window_start_utc is not None:
                capture_starts.append(artifact.capture_window_start_utc)
            if artifact.capture_window_end_utc is not None:
                capture_ends.append(artifact.capture_window_end_utc)
        capture_start = min(capture_starts) if capture_starts else None
        capture_end = max(capture_ends) if capture_ends else None
        capture_start_str = capture_start.isoformat() if capture_start else "Unavailable"
        capture_end_str = capture_end.isoformat() if capture_end else "Unavailable"
        readme_content = README_TEMPLATE.format(
            incident_id=incident_id,
            export_id=export_id,
            capture_start=capture_start_str,
            capture_end=capture_end_str,
        )

        # 6. Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            package_root = "ADC_Court_Package"
            zf.writestr(f"{package_root}/00_README.txt", readme_content)
            zf.writestr(
                f"{package_root}/02_Evidence_Inventory.csv",
                inventory_csv_bytes,
            )
            zf.writestr(
                f"{package_root}/03_Chain_of_Custody.csv",
                coc_csv_bytes,
            )
            zf.writestr(
                f"{package_root}/integrity_appendix.csv",
                appendix_csv_bytes,
            )

            # Include stored artifact files
            for artifact, filename in exportable_artifacts:
                try:
                    artifact_data = s3.download(artifact.s3_key)
                    safe_artifact_type = _safe_artifact_type(artifact.artifact_type)
                    zf.writestr(
                        (
                            f"{package_root}/artifacts/{safe_artifact_type}/"
                            f"{filename}"
                        ),
                        artifact_data,
                    )
                except Exception:
                    logger.warning(
                        "Could not include artifact %s in export",
                        artifact.s3_key,
                        exc_info=True,
                    )

        zip_bytes = zip_buffer.getvalue()

        # 7. Upload ZIP to S3
        zip_key = s3_key_builder.export_key(
            incident_id=incident_id,
            export_id=export_id,
        )
        s3.upload(zip_key, zip_bytes)

        # 8. Update export row to ready
        update_export(
            db,
            export_id=exp_uuid,
            status="ready",
            s3_bucket=settings.S3_BUCKET,
            s3_key=zip_key,
        )

        # 9. Emit EXPORT_GENERATED
        _emit(db, inc_uuid, SystemEventType.EXPORT_GENERATED, {
            "export_id": export_id,
            "s3_key": zip_key,
            "sha256": _hash_bytes(zip_bytes),
            "byte_size": len(zip_bytes),
        })

        return {
            "export_id": export_id,
            "incident_id": incident_id,
            "status": "ready",
        }

    except Exception:
        logger.exception("Export %s failed for incident %s", export_id, incident_id)
        _emit(db, inc_uuid, SystemEventType.EXPORT_FAILED, {
            "export_id": export_id,
        })
        raise

    finally:
        db.close()


# Backward-compatible alias
generate_export = build_export
