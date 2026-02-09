"""Export generation tasks."""

import csv
import hashlib
import io
import logging
import uuid as _uuid
import zipfile

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    3. Generate Evidence Inventory CSV/PDF
    4. Generate Chain-of-Custody CSV/PDF (derived from events)
    5. Bundle artifact files into a ZIP
    6. Upload ZIP to S3
    7. Update export row to ready
    8. Emit EXPORT_GENERATED
    """
    from app.core.config import settings
    from app.db.repo.artifacts import get_artifacts_by_incident
    from app.db.repo.events import get_events_by_incident
    from app.db.repo.exports import update_export
    from app.domain.system_event_types import SystemEventType
    from app.services import s3_key_builder
    from app.services.vault_s3 import VaultS3
    from app.services.pdf_render import render_pdf

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

        # Evidence Inventory PDF
        inventory_pdf_bytes = render_pdf("evidence_inventory", {
            "incident_id": incident_id,
            "artifacts": [
                {
                    "artifact_id": str(a.artifact_id),
                    "artifact_type": a.artifact_type,
                    "status": a.status,
                    "sha256": a.sha256,
                }
                for a in artifacts
            ],
        })

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

        # Chain-of-Custody PDF
        coc_pdf_bytes = render_pdf("chain_of_custody", {
            "incident_id": incident_id,
            "events": [
                {
                    "event_type": ev.event_type,
                    "occurred_at_utc": str(ev.occurred_at_utc),
                    "actor_type": ev.actor_type,
                    "actor_id": ev.actor_id,
                }
                for ev in sorted_events
            ],
        })

        # 5. Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("evidence_inventory.csv", inventory_csv_bytes)
            zf.writestr("evidence_inventory.pdf", inventory_pdf_bytes)
            zf.writestr("chain_of_custody.csv", coc_csv_bytes)
            zf.writestr("chain_of_custody.pdf", coc_pdf_bytes)

            # Include stored artifact files
            for a in artifacts:
                if a.status == "captured" and a.s3_key:
                    try:
                        artifact_data = s3.download(a.s3_key)
                        filename = a.s3_key.rsplit("/", 1)[-1]
                        zf.writestr(f"artifacts/{filename}", artifact_data)
                    except Exception:
                        logger.warning(
                            "Could not include artifact %s in export",
                            a.s3_key,
                            exc_info=True,
                        )

        zip_bytes = zip_buffer.getvalue()

        # 6. Upload ZIP to S3
        zip_key = s3_key_builder.export_key(
            incident_id=incident_id,
            export_id=export_id,
        )
        s3.upload(zip_key, zip_bytes)

        # 7. Update export row to ready
        update_export(
            db,
            export_id=exp_uuid,
            status="ready",
            s3_bucket=settings.S3_BUCKET,
            s3_key=zip_key,
        )

        # 8. Emit EXPORT_GENERATED
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
