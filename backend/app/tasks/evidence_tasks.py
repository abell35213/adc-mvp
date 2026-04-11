"""Evidence collection tasks."""

import hashlib
import logging
import uuid as _uuid
from datetime import datetime, timezone

from app.core.metrics import MetricNames, increment
from app.integrations.errors import as_normalized_error
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
_IDEMPOTENCY_UUID_NAMESPACE = _uuid.UUID("f10f5c65-1d84-42bf-b95c-d6253aac3020")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_bytes(data: bytes) -> str:
    """Return hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _idempotency_key(*parts: str | None) -> str:
    """Return a deterministic idempotency key from stable task inputs."""
    normalized = [p or "none" for p in parts]
    return _hash_bytes("|".join(normalized).encode())


def _deterministic_uuid(key: str) -> _uuid.UUID:
    """Return a stable UUID for a deterministic key."""
    return _uuid.uuid5(_IDEMPOTENCY_UUID_NAMESPACE, key)


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


def _event_exists(db, incident_id, event_type: str, idempotency_key: str) -> bool:
    """Check whether an event with a matching idempotency key already exists."""
    from app.db.repo.events import get_events_by_incident

    existing_events = get_events_by_incident(db, incident_id)
    return any(
        ev.event_type == event_type
        and isinstance(ev.payload, dict)
        and ev.payload.get("idempotency_key") == idempotency_key
        for ev in existing_events
    )


def _emit_once(db, incident_id, event_type, idempotency_key: str, payload=None):
    """Emit an event exactly once for a given idempotency key."""
    full_payload = {
        "idempotency_key": idempotency_key,
        **(payload or {}),
    }
    if _event_exists(db, incident_id, event_type, idempotency_key):
        return None
    return _emit(db, incident_id, event_type, full_payload)


def _artifact_exists(db, artifact_id: _uuid.UUID) -> bool:
    """Check whether an artifact with this deterministic identifier exists."""
    from app.db.models import Artifact

    return db.query(Artifact).filter(Artifact.artifact_id == artifact_id).first() is not None


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
    increment("evidence.capture_dashcam.attempts")
    from app.core.config import settings
    from app.db.repo.artifacts import create_artifact
    from app.db.repo.evidence_requests import (
        create_evidence_request,
        update_evidence_request_error,
    )
    from app.db.repo.integration_operations import (
        create_integration_operation,
        update_integration_operation_error,
    )
    from app.domain.system_event_types import SystemEventType
    from app.services import s3_key_builder
    from app.services.samsara_client import SamsaraClient
    from app.services.vault_s3 import VaultS3

    inc_uuid = _uuid.UUID(incident_id)
    workflow_key = _idempotency_key(
        "evidence", "dashcam", incident_id, window_start, window_end
    )
    ws_dt = _parse_iso(window_start)
    we_dt = _parse_iso(window_end)
    db = _get_db()

    try:
        org_id = _get_org_id(db, inc_uuid)
        # 1. Emit EVIDENCE_CAPTURE_REQUESTED
        if _event_exists(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED,
            workflow_key,
        ):
            return {
                "incident_id": incident_id,
                "type": "dashcam",
                "status": "skipped_duplicate",
                "idempotency_key": workflow_key,
            }

        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_REQUESTED,
            workflow_key,
            {
                "type": "dashcam",
                "window_start": window_start,
                "window_end": window_end,
            },
        )
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED,
            workflow_key,
            {
                "type": "dashcam",
                "window_start": window_start,
                "window_end": window_end,
            },
        )

        samsara = SamsaraClient()
        s3 = VaultS3(bucket=settings.S3_BUCKET, region=settings.AWS_REGION)
        operation = create_integration_operation(
            db,
            org_id=_uuid.UUID(org_id),
            incident_id=inc_uuid,
            provider="samsara",
            domain="dashcam",
            operation_type="capture_dashcam",
            status="running",
            correlation_id=workflow_key,
            payload_json={
                "window_start": window_start,
                "window_end": window_end,
            },
        )

        streams = {
            "road_facing": "dash_cam_video_road",
            "driver_facing": "dash_cam_video_driver",
        }

        for stream_label, artifact_type in streams.items():
            evidence_request = None
            try:
                evidence_request = create_evidence_request(
                    db,
                    org_id=_uuid.UUID(org_id),
                    incident_id=inc_uuid,
                    operation_id=operation.operation_id,
                    provider="samsara",
                    domain="dashcam",
                    correlation_id=workflow_key,
                    external_reference=stream_label,
                    request_payload_json={
                        "stream": stream_label,
                        "window_start": window_start,
                        "window_end": window_end,
                    },
                    status="in_progress",
                )
                # 2. Attempt Samsara call for this stream
                video_bytes = samsara.fetch_dashcam_stream(
                    stream=stream_label,
                    start=window_start,
                    end=window_end,
                )

                if video_bytes is None:
                    raise ValueError(f"No footage returned for {stream_label}")

                # 3a. Upload to S3
                artifact_key = _idempotency_key(
                    workflow_key, stream_label, artifact_type, "video"
                )
                art_id = _deterministic_uuid(artifact_key)
                if _artifact_exists(db, art_id):
                    continue
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
                _emit_once(
                    db,
                    inc_uuid,
                    SystemEventType.ARTIFACT_RECORDED,
                    artifact_key,
                    {
                        "artifact_type": artifact_type,
                        "stream": stream_label,
                        "s3_key": s3_key,
                        "status": "captured",
                    },
                )

                # 3d. Emit ARTIFACT_HASHED
                _emit_once(
                    db,
                    inc_uuid,
                    SystemEventType.ARTIFACT_HASHED,
                    artifact_key,
                    {
                        "artifact_type": artifact_type,
                        "sha256": sha,
                    },
                )

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
                evidence_request.status = "fulfilled"
                evidence_request.response_payload_json = {
                    "artifact_id": str(art_id),
                    "artifact_type": artifact_type,
                    "byte_size": len(video_bytes),
                }
                db.commit()

            except Exception as stream_exc:
                # Stream unavailable — document, don't crash
                normalized_error = as_normalized_error(
                    stream_exc, provider_hint="samsara", category="dashcam"
                )
                logger.warning(
                    "Dashcam stream %s unavailable for incident %s: %s",
                    stream_label,
                    incident_id,
                    normalized_error.operator_message,
                )
                if evidence_request is not None:
                    update_evidence_request_error(db, evidence_request, normalized_error)
                    evidence_request.status = "failed"
                    evidence_request.response_payload_json = normalized_error.to_dict()
                    db.commit()
                update_integration_operation_error(db, operation, normalized_error)

                _emit_once(
                    db,
                    inc_uuid,
                    SystemEventType.ARTIFACT_RECORDED,
                    _idempotency_key(workflow_key, stream_label, artifact_type, "unavailable"),
                    {
                        "artifact_type": artifact_type,
                        "stream": stream_label,
                        "status": "unavailable",
                        "reason": normalized_error.user_facing_message,
                        "error_code": normalized_error.code,
                        "retryable": normalized_error.retryable,
                    },
                )

                unavailable_key = _idempotency_key(
                    workflow_key, stream_label, artifact_type, "unavailable"
                )
                unavailable_art_id = _deterministic_uuid(unavailable_key)
                if not _artifact_exists(db, unavailable_art_id):
                    create_artifact(
                        db,
                        incident_id=inc_uuid,
                        artifact_type=artifact_type,
                        status="unavailable",
                        artifact_id=unavailable_art_id,
                        capture_window_start_utc=ws_dt,
                        capture_window_end_utc=we_dt,
                        unavailable_reason_code="stream_unavailable",
                        unavailable_reason_detail=normalized_error.user_facing_message,
                    )

        # 4. Emit EVIDENCE_CAPTURE_SUCCEEDED
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED,
            workflow_key,
            {
                "type": "dashcam",
            },
        )
        operation.status = "succeeded"
        db.commit()

        return {
            "incident_id": incident_id,
            "type": "dashcam",
            "status": "captured",
            "idempotency_key": workflow_key,
        }

    except Exception as exc:
        logger.exception("Dashcam capture failed for incident %s", incident_id)
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_FAILED,
            workflow_key,
            {
                "type": "dashcam",
                "reason": str(exc),
            },
        )
        increment(MetricNames.CELERY_TASK_FAILURES)
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
    increment("evidence.capture_telematics.attempts")
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
    workflow_key = _idempotency_key(
        "evidence", "telematics", incident_id, window_start, window_end
    )
    ws_dt = _parse_iso(window_start)
    we_dt = _parse_iso(window_end)
    db = _get_db()

    try:
        org_id = _get_org_id(db, inc_uuid)
        if _event_exists(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED,
            workflow_key,
        ):
            return {
                "incident_id": incident_id,
                "type": "telematics",
                "status": "skipped_duplicate",
                "idempotency_key": workflow_key,
            }

        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_REQUESTED,
            workflow_key,
            {
                "type": "telematics",
                "window_start": window_start,
                "window_end": window_end,
            },
        )
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED,
            workflow_key,
            {
                "type": "telematics",
                "window_start": window_start,
                "window_end": window_end,
            },
        )

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
                json_key_id = _idempotency_key(
                    workflow_key, dataset_name, spec["artifact_type"], "json"
                )
                json_art_id = _deterministic_uuid(json_key_id)
                json_key = s3_key_builder.telematics_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    artifact_type=spec["artifact_type"],
                    artifact_id=str(json_art_id),
                    extension="json",
                )
                if not _artifact_exists(db, json_art_id):
                    s3.put_bytes(json_key, json_bytes)
                    json_sha = _hash_bytes(json_bytes)

                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.ARTIFACT_RECORDED,
                        json_key_id,
                        {
                            "artifact_type": spec["artifact_type"],
                            "format": "json",
                            "s3_key": json_key,
                            "status": "captured",
                        },
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.ARTIFACT_HASHED,
                        json_key_id,
                        {
                            "artifact_type": spec["artifact_type"],
                            "format": "json",
                            "sha256": json_sha,
                        },
                    )

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

                csv_key_id = _idempotency_key(
                    workflow_key, dataset_name, spec["artifact_type"], "csv"
                )
                csv_art_id = _deterministic_uuid(csv_key_id)
                csv_key = s3_key_builder.telematics_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    artifact_type=spec["artifact_type"],
                    artifact_id=str(csv_art_id),
                    extension="csv",
                )
                if not _artifact_exists(db, csv_art_id):
                    s3.put_bytes(csv_key, csv_bytes)
                    csv_sha = _hash_bytes(csv_bytes)

                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.ARTIFACT_RECORDED,
                        csv_key_id,
                        {
                            "artifact_type": spec["artifact_type"],
                            "format": "csv",
                            "s3_key": csv_key,
                            "status": "captured",
                        },
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.ARTIFACT_HASHED,
                        csv_key_id,
                        {
                            "artifact_type": spec["artifact_type"],
                            "format": "csv",
                            "sha256": csv_sha,
                        },
                    )

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
                pdf_key_id = _idempotency_key(
                    workflow_key, dataset_name, spec["artifact_type"], "pdf"
                )
                pdf_art_id = _deterministic_uuid(pdf_key_id)
                pdf_key = s3_key_builder.telematics_key(
                    org_id=org_id,
                    incident_id=incident_id,
                    artifact_type=spec["artifact_type"],
                    artifact_id=str(pdf_art_id),
                    extension="pdf",
                )
                if not _artifact_exists(db, pdf_art_id):
                    s3.put_bytes(pdf_key, pdf_bytes)
                    pdf_sha = _hash_bytes(pdf_bytes)

                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.ARTIFACT_RECORDED,
                        pdf_key_id,
                        {
                            "artifact_type": spec["artifact_type"],
                            "format": "pdf",
                            "s3_key": pdf_key,
                            "status": "captured",
                        },
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.ARTIFACT_HASHED,
                        pdf_key_id,
                        {
                            "artifact_type": spec["artifact_type"],
                            "format": "pdf",
                            "sha256": pdf_sha,
                        },
                    )

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
                    dataset_name,
                    incident_id,
                    reason,
                )

                _emit_once(
                    db,
                    inc_uuid,
                    SystemEventType.ARTIFACT_RECORDED,
                    _idempotency_key(workflow_key, dataset_name, "unavailable"),
                    {
                        "artifact_type": spec["artifact_type"],
                        "status": "unavailable",
                        "reason": reason,
                    },
                )

                unavailable_key = _idempotency_key(
                    workflow_key, dataset_name, "unavailable"
                )
                unavailable_art_id = _deterministic_uuid(unavailable_key)
                if not _artifact_exists(db, unavailable_art_id):
                    create_artifact(
                        db,
                        incident_id=inc_uuid,
                        artifact_type=spec["artifact_type"],
                        status="unavailable",
                        artifact_id=unavailable_art_id,
                        capture_window_start_utc=ws_dt,
                        capture_window_end_utc=we_dt,
                        unavailable_reason_code="dataset_unavailable",
                        unavailable_reason_detail=reason,
                    )

        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED,
            workflow_key,
            {
                "type": "telematics",
            },
        )

        return {
            "incident_id": incident_id,
            "type": "telematics",
            "status": "captured",
            "idempotency_key": workflow_key,
        }

    except Exception as exc:
        logger.exception("Telematics capture failed for incident %s", incident_id)
        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_FAILED,
            workflow_key,
            {
                "type": "telematics",
                "reason": str(exc),
            },
        )
        increment(MetricNames.CELERY_TASK_FAILURES)
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
