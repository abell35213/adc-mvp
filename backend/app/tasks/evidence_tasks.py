"""Evidence collection tasks."""

import hashlib
import logging
import uuid as _uuid
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_bytes(data: bytes) -> str:
    """Return hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string to a timezone-aware datetime, or None."""
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


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


# ---------------------------------------------------------------------------
# Task: capture_dashcam
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
)
def capture_dashcam(
    self, incident_id: str, window_start: str | None, window_end: str | None
):
    """Capture dashcam footage for an incident.

    Steps:
    1. Emit EVIDENCE_CAPTURE_REQUESTED (type=dashcam, window)
    2. Attempt Samsara calls (road-facing + driver-facing)
    3. For each stream: download → upload S3 → hash → emit events → record artifact
    4. Emit EVIDENCE_CAPTURE_SUCCEEDED when complete
    """
    from app.core.config import settings
    from app.db.repo.artifacts import create_artifact
    from app.domain.system_event_types import SystemEventType
    from app.services import s3_key_builder
    from app.services.samsara_client import SamsaraClient
    from app.services.vault_s3 import VaultS3

    inc_uuid = _uuid.UUID(incident_id)
    ws_dt = _parse_iso(window_start)
    we_dt = _parse_iso(window_end)
    db = _get_db()

    try:
        org_id = _get_org_id(db, inc_uuid)
        # 1. Emit EVIDENCE_CAPTURE_REQUESTED
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_REQUESTED, {
            "type": "dashcam",
            "window_start": window_start,
            "window_end": window_end,
        })
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED, {
            "type": "dashcam",
            "window_start": window_start,
            "window_end": window_end,
        })

        samsara = SamsaraClient()
        s3 = VaultS3(bucket=settings.S3_BUCKET, region=settings.AWS_REGION)

        streams = {
            "road_facing": "dash_cam_video_road",
            "driver_facing": "dash_cam_video_driver",
        }

        for stream_label, artifact_type in streams.items():
            try:
                # 2. Attempt Samsara call for this stream
                video_bytes = samsara.fetch_dashcam_stream(
                    stream=stream_label,
                    start=window_start,
                    end=window_end,
                )

                if video_bytes is None:
                    raise ValueError(f"No footage returned for {stream_label}")

                # 3a. Upload to S3
                art_id = _uuid.uuid4()
                s3_key = s3_key_builder.dashcam_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    camera_view=stream_label,
                    artifact_id=str(art_id),
                )
                s3.put_bytes(s3_key, video_bytes)

                # 3b. Compute SHA-256
                sha = _hash_bytes(video_bytes)

                # 3c. Emit ARTIFACT_RECORDED
                _emit(db, inc_uuid, SystemEventType.ARTIFACT_RECORDED, {
                    "artifact_type": artifact_type,
                    "stream": stream_label,
                    "s3_key": s3_key,
                    "status": "captured",
                })

                # 3d. Emit ARTIFACT_HASHED
                _emit(db, inc_uuid, SystemEventType.ARTIFACT_HASHED, {
                    "artifact_type": artifact_type,
                    "sha256": sha,
                })

                # 3e. Insert artifact row
                create_artifact(
                    db,
                    incident_id=inc_uuid,
                    artifact_type=artifact_type,
                    status="captured",
                    artifact_id=art_id,
                    capture_window_start_utc=ws_dt,
                    capture_window_end_utc=we_dt,
                    s3_bucket=settings.S3_BUCKET,
                    s3_key=s3_key,
                    sha256=sha,
                    byte_size=len(video_bytes),
                )

            except Exception as stream_exc:
                # Stream unavailable — document, don't crash
                reason = str(stream_exc)
                logger.warning(
                    "Dashcam stream %s unavailable for incident %s: %s",
                    stream_label, incident_id, reason,
                )

                _emit(db, inc_uuid, SystemEventType.ARTIFACT_RECORDED, {
                    "artifact_type": artifact_type,
                    "stream": stream_label,
                    "status": "unavailable",
                    "reason": reason,
                })

                create_artifact(
                    db,
                    incident_id=inc_uuid,
                    artifact_type=artifact_type,
                    status="unavailable",
                    capture_window_start_utc=ws_dt,
                    capture_window_end_utc=we_dt,
                    unavailable_reason_code="stream_unavailable",
                    unavailable_reason_detail=reason,
                )

        # 4. Emit EVIDENCE_CAPTURE_SUCCEEDED
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED, {
            "type": "dashcam",
        })

        return {"incident_id": incident_id, "type": "dashcam", "status": "captured"}

    except Exception as exc:
        logger.exception("Dashcam capture failed for incident %s", incident_id)
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_FAILED, {
            "type": "dashcam",
            "reason": str(exc),
        })
        raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task: capture_telematics_bundle
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=360,
)
def capture_telematics_bundle(
    self, incident_id: str, window_start: str | None, window_end: str | None
):
    """Capture telematics bundle for an incident.

    For each dataset (ELD, GPS, safety events, vehicle state):
    1. Fetch raw data via Samsara
    2. Normalize records
    3. Validate JSON schema
    4. Upload JSON to S3, compute SHA-256
    5. Generate CSV/PDF renderings, upload each, compute SHA-256
    6. Record artifact metadata and emit events
    """
    import json
    import csv
    import io

    from app.core.config import settings
    from app.db.repo.artifacts import create_artifact
    from app.domain.system_event_types import SystemEventType
    from app.services import s3_key_builder
    from app.services.samsara_client import SamsaraClient
    from app.services.vault_s3 import VaultS3
    from app.services.schema_validate import validate_payload
    from app.services.pdf_render import render_pdf
    from app.services.normalizers.eld import normalize_eld_record
    from app.services.normalizers.gps import normalize_gps_record
    from app.services.normalizers.safety_events import normalize_safety_event
    from app.services.normalizers.vehicle_state import normalize_vehicle_state

    inc_uuid = _uuid.UUID(incident_id)
    ws_dt = _parse_iso(window_start)
    we_dt = _parse_iso(window_end)
    db = _get_db()

    try:
        org_id = _get_org_id(db, inc_uuid)
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_REQUESTED, {
            "type": "telematics",
            "window_start": window_start,
            "window_end": window_end,
        })
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED, {
            "type": "telematics",
            "window_start": window_start,
            "window_end": window_end,
        })

        samsara = SamsaraClient()
        s3 = VaultS3(bucket=settings.S3_BUCKET, region=settings.AWS_REGION)

        datasets = {
            "eld": {
                "artifact_type": "eld_log",
                "normalizer": normalize_eld_record,
                "schema_name": "eld_log",
                "fetcher": "get_eld_logs",
            },
            "gps": {
                "artifact_type": "gps_trail",
                "normalizer": normalize_gps_record,
                "schema_name": "gps_trail",
                "fetcher": "get_vehicle_locations",
            },
            "safety_events": {
                "artifact_type": "safety_event",
                "normalizer": normalize_safety_event,
                "schema_name": "safety_event",
                "fetcher": "get_safety_events",
            },
            "vehicle_state": {
                "artifact_type": "vehicle_state",
                "normalizer": normalize_vehicle_state,
                "schema_name": "vehicle_state",
                "fetcher": "get_vehicle_state",
            },
        }

        for dataset_name, spec in datasets.items():
            try:
                # 1. Fetch raw data
                fetcher = getattr(samsara, spec["fetcher"], None)
                if fetcher is None:
                    raise AttributeError(
                        f"SamsaraClient has no method {spec['fetcher']}"
                    )
                raw_records = fetcher(
                    start=window_start,
                    end=window_end,
                )
                if raw_records is None:
                    raw_records = []

                # 2. Normalize
                normalized = [spec["normalizer"](r) for r in raw_records]

                # 3. Validate JSON schema
                for record in normalized:
                    validate_payload(record, spec["schema_name"])

                # 4. Upload JSON to S3
                json_bytes = json.dumps(normalized, default=str).encode()
                json_art_id = _uuid.uuid4()
                json_key = s3_key_builder.telematics_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    artifact_type=spec["artifact_type"],
                    artifact_id=str(json_art_id),
                    extension="json",
                )
                s3.put_bytes(json_key, json_bytes)
                json_sha = _hash_bytes(json_bytes)

                _emit(db, inc_uuid, SystemEventType.ARTIFACT_RECORDED, {
                    "artifact_type": spec["artifact_type"],
                    "format": "json",
                    "s3_key": json_key,
                    "status": "captured",
                })
                _emit(db, inc_uuid, SystemEventType.ARTIFACT_HASHED, {
                    "artifact_type": spec["artifact_type"],
                    "format": "json",
                    "sha256": json_sha,
                })

                create_artifact(
                    db,
                    incident_id=inc_uuid,
                    artifact_type=spec["artifact_type"],
                    status="captured",
                    artifact_id=json_art_id,
                    capture_window_start_utc=ws_dt,
                    capture_window_end_utc=we_dt,
                    s3_bucket=settings.S3_BUCKET,
                    s3_key=json_key,
                    sha256=json_sha,
                    byte_size=len(json_bytes),
                )

                # 5. Generate CSV rendering
                if normalized:
                    buf = io.StringIO()
                    writer = csv.DictWriter(buf, fieldnames=normalized[0].keys())
                    writer.writeheader()
                    writer.writerows(normalized)
                    csv_bytes = buf.getvalue().encode()
                else:
                    csv_bytes = b""

                csv_art_id = _uuid.uuid4()
                csv_key = s3_key_builder.telematics_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    artifact_type=spec["artifact_type"],
                    artifact_id=str(csv_art_id),
                    extension="csv",
                )
                s3.put_bytes(csv_key, csv_bytes)
                csv_sha = _hash_bytes(csv_bytes)

                _emit(db, inc_uuid, SystemEventType.ARTIFACT_RECORDED, {
                    "artifact_type": spec["artifact_type"],
                    "format": "csv",
                    "s3_key": csv_key,
                    "status": "captured",
                })
                _emit(db, inc_uuid, SystemEventType.ARTIFACT_HASHED, {
                    "artifact_type": spec["artifact_type"],
                    "format": "csv",
                    "sha256": csv_sha,
                })

                create_artifact(
                    db,
                    incident_id=inc_uuid,
                    artifact_type=spec["artifact_type"],
                    status="captured",
                    artifact_id=csv_art_id,
                    capture_window_start_utc=ws_dt,
                    capture_window_end_utc=we_dt,
                    s3_bucket=settings.S3_BUCKET,
                    s3_key=csv_key,
                    sha256=csv_sha,
                    byte_size=len(csv_bytes),
                )

                # 6. Generate PDF rendering
                pdf_bytes = render_pdf(
                    f"{dataset_name}_report",
                    {"records": normalized, "incident_id": incident_id},
                )
                pdf_art_id = _uuid.uuid4()
                pdf_key = s3_key_builder.telematics_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    artifact_type=spec["artifact_type"],
                    artifact_id=str(pdf_art_id),
                    extension="pdf",
                )
                s3.put_bytes(pdf_key, pdf_bytes)
                pdf_sha = _hash_bytes(pdf_bytes)

                _emit(db, inc_uuid, SystemEventType.ARTIFACT_RECORDED, {
                    "artifact_type": spec["artifact_type"],
                    "format": "pdf",
                    "s3_key": pdf_key,
                    "status": "captured",
                })
                _emit(db, inc_uuid, SystemEventType.ARTIFACT_HASHED, {
                    "artifact_type": spec["artifact_type"],
                    "format": "pdf",
                    "sha256": pdf_sha,
                })

                create_artifact(
                    db,
                    incident_id=inc_uuid,
                    artifact_type=spec["artifact_type"],
                    status="captured",
                    artifact_id=pdf_art_id,
                    capture_window_start_utc=ws_dt,
                    capture_window_end_utc=we_dt,
                    s3_bucket=settings.S3_BUCKET,
                    s3_key=pdf_key,
                    sha256=pdf_sha,
                    byte_size=len(pdf_bytes),
                )

            except Exception as ds_exc:
                reason = str(ds_exc)
                logger.warning(
                    "Telematics dataset %s unavailable for incident %s: %s",
                    dataset_name, incident_id, reason,
                )

                _emit(db, inc_uuid, SystemEventType.ARTIFACT_RECORDED, {
                    "artifact_type": spec["artifact_type"],
                    "status": "unavailable",
                    "reason": reason,
                })

                create_artifact(
                    db,
                    incident_id=inc_uuid,
                    artifact_type=spec["artifact_type"],
                    status="unavailable",
                    capture_window_start_utc=ws_dt,
                    capture_window_end_utc=we_dt,
                    unavailable_reason_code="dataset_unavailable",
                    unavailable_reason_detail=reason,
                )

        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED, {
            "type": "telematics",
        })

        return {"incident_id": incident_id, "type": "telematics", "status": "captured"}

    except Exception as exc:
        logger.exception("Telematics capture failed for incident %s", incident_id)
        _emit(db, inc_uuid, SystemEventType.EVIDENCE_CAPTURE_FAILED, {
            "type": "telematics",
            "reason": str(exc),
        })
        raise

    finally:
        db.close()


# Backward-compatible alias
capture_telematics = capture_telematics_bundle


@celery_app.task
def collect_evidence(incident_id: str):
    """Collect all evidence artifacts for an incident."""
    # Placeholder: orchestrate evidence collection
    return {"incident_id": incident_id, "status": "collected"}
