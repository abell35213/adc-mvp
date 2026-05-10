"""Evidence collection tasks."""

import hashlib
import logging
import uuid as _uuid
from datetime import datetime, timezone

from app.core.metrics import MetricNames, increment
from app.integrations.errors import as_normalized_error
from app.jobs.retry_policy import (
    classify_normalized_error,
    compute_retry_delay_seconds,
    get_policy_for_capability,
)
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


def _admin_action_for_reason(reason_code: str) -> str:
    if reason_code == "credentials_invalid":
        return "reauth_required"
    if reason_code == "vehicle_mapping_missing":
        return "mapping_fix_required"
    return "manual_investigation_required"


def _reason_from_normalized_error(normalized_error) -> str:
    code = normalized_error.code
    if code in {"AUTH_INVALID_CREDENTIALS", "TELEMATICS_AUTH_FAILED"}:
        return "credentials_invalid"
    if code in {"TELEMATICS_NOT_MAPPED", "MAPPING_NOT_FOUND", "MAPPING_INVALID_REFERENCE"}:
        return "vehicle_mapping_missing"
    return normalized_error.code.lower()


@celery_app.task(bind=True, acks_late=True, max_retries=0, soft_time_limit=120, time_limit=150)
def capture_weather_snapshot(
    self,
    incident_id: str,
    window_start: str | None,
    window_end: str | None,
):
    """Capture incident weather snapshot asynchronously."""
    from app.db.models import Incident
    from app.services.weather_snapshot_service import capture_weather_snapshot_if_missing

    db = _get_db()
    try:
        incident = db.query(Incident).filter(Incident.incident_id == _uuid.UUID(incident_id)).first()
        if incident is None:
            logger.warning("Weather snapshot task skipped: incident %s not found", incident_id)
            return {"incident_id": incident_id, "status": "incident_not_found"}
        capture_weather_snapshot_if_missing(
            db,
            incident=incident,
            request_window_start=_parse_iso(window_start),
            request_window_end=_parse_iso(window_end),
        )
        return {"incident_id": incident_id, "status": "ok"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task: capture_dashcam
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=4,
    soft_time_limit=600,
    time_limit=660,
)
def capture_dashcam(
    self,
    incident_id: str,
    window_start: str | None,
    window_end: str | None,
    operation_id: str | None = None,
    correlation_id: str | None = None,
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
    from app.db.models import EvidenceRequest, IntegrationOperation
    from app.db.repo.evidence_requests import create_evidence_request, update_evidence_request_error
    from app.db.repo.integration_operations import create_integration_operation, update_integration_operation_error
    from app.domain.system_event_types import SystemEventType
    from app.services.integration_health_service import (
        set_evidence_request_status,
        transition_operation_status,
    )
    from app.services.dashcam_reason_codes import map_dashcam_missing_reason_code
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
        operation = None
        if operation_id:
            operation = (
                db.query(IntegrationOperation)
                .filter(IntegrationOperation.operation_id == _uuid.UUID(operation_id))
                .first()
            )
        if operation is None:
            operation = create_integration_operation(
                db,
                org_id=_uuid.UUID(org_id),
                incident_id=inc_uuid,
                provider="samsara",
                domain="dashcam",
                operation_type="capture_dashcam",
                status="requested",
                correlation_id=correlation_id or workflow_key,
                payload_json={
                    "window_start": window_start,
                    "window_end": window_end,
                },
            )
        transition_operation_status(
            db,
            operation=operation,
            to_status="submitted_to_provider",
            message="Dashcam request submitted to provider",
        )
        transition_operation_status(
            db,
            operation=operation,
            to_status="processing_at_provider",
            message="Dashcam request processing at provider",
        )

        streams = {
            "road_facing": "dash_cam_video_road",
            "driver_facing": "dash_cam_video_driver",
        }
        captured_stream_count = 0
        unavailable_stream_count = 0
        stream_count = len(streams)

        for stream_label, artifact_type in streams.items():
            evidence_request = None
            try:
                provider_request_id = f"{incident_id}:{stream_label}:{window_start or 'na'}:{window_end or 'na'}"
                transition_operation_status(
                    db,
                    operation=operation,
                    to_status="processing_at_provider",
                    message=f"Polling provider for {stream_label}",
                    external_reference_id=provider_request_id,
                )
                evidence_request = (
                    db.query(EvidenceRequest)
                    .filter(
                        EvidenceRequest.incident_id == inc_uuid,
                        EvidenceRequest.operation_id == operation.operation_id,
                        EvidenceRequest.external_reference == stream_label,
                    )
                    .first()
                )
                if evidence_request is None:
                    evidence_request = create_evidence_request(
                        db,
                        org_id=_uuid.UUID(org_id),
                        incident_id=inc_uuid,
                        operation_id=operation.operation_id,
                        provider="samsara",
                        domain="dashcam",
                        correlation_id=correlation_id or workflow_key,
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
                transition_operation_status(
                    db,
                    operation=operation,
                    to_status="available",
                    message=f"Dashcam clip available for {stream_label}",
                    external_reference_id=provider_request_id,
                )

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
                        "correlation_id": correlation_id or workflow_key,
                        "operation_id": str(operation.operation_id) if operation is not None else None,
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
                set_evidence_request_status(
                    db,
                    evidence_request=evidence_request,
                    status="fulfilled",
                    response_payload_json={
                        "artifact_id": str(art_id),
                        "artifact_type": artifact_type,
                        "byte_size": len(video_bytes),
                    },
                )
                captured_stream_count += 1

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
                    set_evidence_request_status(
                        db,
                        evidence_request=evidence_request,
                        status="failed",
                        response_payload_json=normalized_error.to_dict(),
                    )
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
                        "correlation_id": correlation_id or workflow_key,
                        "operation_id": str(operation.operation_id) if operation is not None else None,
                    },
                )

                unavailable_key = _idempotency_key(
                    workflow_key, stream_label, artifact_type, "unavailable"
                )
                unavailable_art_id = _deterministic_uuid(unavailable_key)
                reason_code = map_dashcam_missing_reason_code(
                    normalized_error=normalized_error,
                    operator_message=str(stream_exc),
                )
                if not _artifact_exists(db, unavailable_art_id):
                    create_artifact(
                        db,
                        incident_id=inc_uuid,
                        artifact_type=artifact_type,
                        status="unavailable",
                        artifact_id=unavailable_art_id,
                        capture_window_start_utc=ws_dt,
                        capture_window_end_utc=we_dt,
                        unavailable_reason_code=reason_code,
                        unavailable_reason_detail=normalized_error.user_facing_message,
                    )
                unavailable_stream_count += 1

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
        final_status = "downloaded" if captured_stream_count > 0 else "unavailable"
        transition_operation_status(db, operation=operation, to_status=final_status, message="Dashcam task finalized")

        return {
            "incident_id": incident_id,
            "type": "dashcam",
            "status": "captured" if captured_stream_count else "unavailable",
            "idempotency_key": workflow_key,
            "captured_streams": captured_stream_count,
            "unavailable_streams": unavailable_stream_count,
            "stream_count": stream_count,
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
        if "operation" in locals() and operation is not None:
            transition_operation_status(
                db,
                operation=operation,
                to_status="failed",
                message=f"Dashcam capture task failed: {exc}",
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
    self,
    incident_id: str,
    window_start: str | None,
    window_end: str | None,
    operation_id: str | None = None,
    correlation_id: str | None = None,
    dataset_windows: dict[str, dict[str, str]] | None = None,
    external_mappings: dict[str, str | None] | None = None,
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
    from app.db.models import EvidenceRequest, IntegrationOperation, Incident
    from app.db.repo.artifacts import create_artifact
    from app.db.repo.evidence_requests import update_evidence_request_error
    from app.db.repo.integration_operations import update_integration_operation_error
    from app.domain.system_event_types import SystemEventType
    from app.integrations.errors import NormalizedIntegrationError
    from app.services.integration_health_service import (
        mark_connection_intervention_required,
        set_evidence_request_status,
        transition_operation_status,
    )
    from app.services import s3_key_builder
    from app.services.samsara_client import SamsaraClient
    from app.services.vault_s3 import VaultS3
    from app.services.schema_validate import validate_payload
    from app.services.pdf_render import render_pdf
    from app.services.telematics_pdf_context import build_telematics_pdf_context
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
        operation = None
        if operation_id:
            operation = (
                db.query(IntegrationOperation)
                .filter(IntegrationOperation.operation_id == _uuid.UUID(operation_id))
                .first()
            )
        if operation is None:
            from app.db.repo.integration_operations import create_integration_operation

            operation = create_integration_operation(
                db,
                org_id=_uuid.UUID(org_id),
                incident_id=inc_uuid,
                provider="samsara",
                domain="telematics",
                operation_type="capture_telematics_bundle",
                status="queued",
                correlation_id=correlation_id or workflow_key,
                payload_json={"window_start": window_start, "window_end": window_end},
            )
        transition_operation_status(
            db,
            operation=operation,
            to_status="running",
            message="Telematics capture task started",
        )
        if dataset_windows is None:
            dataset_windows = {}
        if external_mappings is None:
            external_mappings = {}

        def _telematics_reason(error: Exception) -> str:
            msg = str(error).lower()
            if "401" in msg or "403" in msg or "credential" in msg or "auth" in msg:
                return "credentials_invalid"
            if "mapping" in msg:
                return "vehicle_mapping_missing"
            if "not found" in msg or "no data" in msg or "empty" in msg:
                return "data_not_found"
            return "provider_unavailable"

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

        incident_row = db.query(Incident).filter(Incident.incident_id == inc_uuid).first()
        resolved_vehicle_id = (
            external_mappings.get("vehicle_id")
            if external_mappings.get("vehicle_id")
            else (
                incident_row.samsara_vehicle_id
                if incident_row and incident_row.samsara_vehicle_id
                else (incident_row.adc_vehicle_id if incident_row else None)
            )
        )
        if not resolved_vehicle_id:
            mapping_error = NormalizedIntegrationError(
                code="TELEMATICS_NOT_MAPPED",
                category="telematics",
                provider_key="samsara",
                retryable=False,
                user_facing_message="Vehicle mapping is missing for telematics capture.",
                operator_message="vehicle_mapping_missing",
            )
            update_integration_operation_error(db, operation, mapping_error)
            mark_connection_intervention_required(
                db,
                org_id=_uuid.UUID(org_id),
                provider="samsara",
                domain="telematics",
                reason_code="vehicle_mapping_missing",
                admin_action="mapping_fix_required",
                message="Vehicle mapping is missing for telematics capture.",
            )
            transition_operation_status(
                db,
                operation=operation,
                to_status="failed",
                message="Telematics capture failed: vehicle_mapping_missing",
            )
            return {
                "incident_id": incident_id,
                "type": "telematics",
                "status": "failed",
                "reason_code": "vehicle_mapping_missing",
                "idempotency_key": workflow_key,
            }

        request_statuses: dict[str, dict[str, str]] = {}

        for dataset_name, spec in datasets.items():
            evidence_request = None
            try:
                evidence_request = (
                    db.query(EvidenceRequest)
                    .filter(
                        EvidenceRequest.incident_id == inc_uuid,
                        EvidenceRequest.operation_id == operation.operation_id,
                        EvidenceRequest.external_reference == dataset_name,
                    )
                    .first()
                )
                if evidence_request is None:
                    from app.db.repo.evidence_requests import create_evidence_request

                    evidence_request = create_evidence_request(
                        db,
                        org_id=_uuid.UUID(org_id),
                        incident_id=inc_uuid,
                        operation_id=operation.operation_id,
                        provider="samsara",
                        domain="telematics",
                        correlation_id=correlation_id or workflow_key,
                        external_reference=dataset_name,
                        request_payload_json={
                            "dataset": dataset_name,
                            "window_start": window_start,
                            "window_end": window_end,
                        },
                        status="in_progress",
                    )
                # 1. Fetch raw data
                fetcher = getattr(samsara, spec["fetcher"], None)
                if fetcher is None:
                    raise AttributeError(
                        f"SamsaraClient has no method {spec['fetcher']}"
                    )
                dataset_window = dataset_windows.get(dataset_name, {})
                start = dataset_window.get("start") or window_start
                end = dataset_window.get("end") or window_end
                raw_records = fetcher(start=start, end=end)
                if raw_records is None:
                    raw_records = []
                raw_records = [
                    rec for rec in raw_records if not resolved_vehicle_id or rec.get("vehicleId") == resolved_vehicle_id
                ]

                # 2. Normalize
                normalized = [spec["normalizer"](r) for r in raw_records]
                capture_status = "available" if normalized else "unavailable"
                reason_code = None if normalized else "data_not_found"

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
                            "correlation_id": correlation_id or workflow_key,
                            "operation_id": str(operation.operation_id) if operation is not None else None,
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
                            "correlation_id": correlation_id or workflow_key,
                            "operation_id": str(operation.operation_id) if operation is not None else None,
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
                            "correlation_id": correlation_id or workflow_key,
                            "operation_id": str(operation.operation_id) if operation is not None else None,
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
                            "correlation_id": correlation_id or workflow_key,
                            "operation_id": str(operation.operation_id) if operation is not None else None,
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
                    build_telematics_pdf_context(
                        dataset_name=dataset_name,
                        records=normalized,
                        incident_id=incident_id,
                        window_start_utc=start,
                        window_end_utc=end,
                    ),
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
                            "correlation_id": correlation_id or workflow_key,
                            "operation_id": str(operation.operation_id) if operation is not None else None,
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
                            "correlation_id": correlation_id or workflow_key,
                            "operation_id": str(operation.operation_id) if operation is not None else None,
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
                set_evidence_request_status(
                    db,
                    evidence_request=evidence_request,
                    status="fulfilled",
                    response_payload_json={
                        "dataset": dataset_name,
                        "status": capture_status,
                        "reason_code": reason_code,
                        "window": {"start": start, "end": end},
                        "external_mappings": external_mappings,
                        "raw_record_count": len(raw_records),
                        "normalized_record_count": len(normalized),
                        "raw_payload_reference": {
                            "provider": "samsara",
                            "dataset": dataset_name,
                            "window": {"start": start, "end": end},
                        },
                    },
                )
                request_statuses[dataset_name] = {
                    "status": capture_status,
                    "reason_code": reason_code,
                }

            except Exception as ds_exc:
                reason = str(ds_exc)
                reason_code = _telematics_reason(ds_exc)
                if reason_code == "credentials_invalid":
                    increment(MetricNames.INTEGRATION_PROVIDER_AUTH_FAILURE)
                elif reason_code == "provider_unavailable":
                    increment(MetricNames.INTEGRATION_PROVIDER_FAILURE)
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
                        "reason_code": reason_code,
                        "correlation_id": correlation_id or workflow_key,
                        "operation_id": str(operation.operation_id) if operation is not None else None,
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
                if evidence_request is not None:
                    normalized_error = NormalizedIntegrationError(
                        code="TELEMATICS_UNAVAILABLE",
                        category="telematics",
                        provider_key="samsara",
                        retryable=reason_code != "credentials_invalid",
                        user_facing_message="Telematics data capture failed for one dataset.",
                        operator_message=reason,
                    )
                    update_evidence_request_error(db, evidence_request, normalized_error)
                    set_evidence_request_status(
                        db,
                        evidence_request=evidence_request,
                        status="failed",
                        response_payload_json={
                            "dataset": dataset_name,
                            "status": "failed",
                            "reason_code": reason_code,
                            "error": reason,
                        },
                    )
                request_statuses[dataset_name] = {"status": "failed", "reason_code": reason_code}

        available_count = sum(1 for status in request_statuses.values() if status["status"] == "available")
        failed_count = sum(1 for status in request_statuses.values() if status["status"] == "failed")
        unavailable_count = sum(1 for status in request_statuses.values() if status["status"] == "unavailable")
        overall_status = "available"
        if failed_count == len(datasets):
            overall_status = "failed"
        elif failed_count > 0 or unavailable_count > 0:
            overall_status = "partial"
            increment(MetricNames.EVIDENCE_PARTIAL_RESULT)
        elif available_count == 0:
            overall_status = "unavailable"
            increment(MetricNames.EVIDENCE_UNAVAILABLE_RESULT)
        operation.result_json = {
            "status": overall_status,
            "request_statuses": request_statuses,
            "external_mappings": external_mappings,
        }
        db.add(operation)
        db.commit()

        _emit_once(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED,
            workflow_key,
            {
                "type": "telematics",
            },
        )
        transition_operation_status(
            db,
            operation=operation,
            to_status="succeeded",
            message="Telematics capture task succeeded",
        )

        return {
            "incident_id": incident_id,
            "type": "telematics",
            "status": overall_status,
            "idempotency_key": workflow_key,
        }

    except Exception as exc:
        logger.exception("Telematics capture failed for incident %s", incident_id)
        error_message = str(exc).lower()
        if "credentials_invalid" in error_message:
            normalized_error = NormalizedIntegrationError(
                code="TELEMATICS_AUTH_FAILED",
                category="telematics",
                provider_key="samsara",
                retryable=False,
                user_facing_message="Integration credentials are invalid. Re-authentication is required.",
                operator_message="credentials_invalid",
            )
        elif "vehicle_mapping_missing" in error_message:
            normalized_error = NormalizedIntegrationError(
                code="TELEMATICS_NOT_MAPPED",
                category="telematics",
                provider_key="samsara",
                retryable=False,
                user_facing_message="Vehicle mapping is missing for telematics capture.",
                operator_message="vehicle_mapping_missing",
            )
        else:
            normalized_error = as_normalized_error(
                exc,
                provider_hint="samsara",
                category="telematics",
            )
        reason_code = _reason_from_normalized_error(normalized_error)
        retry_class = classify_normalized_error(normalized_error)
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
        if "operation" in locals() and operation is not None:
            update_integration_operation_error(db, operation, normalized_error)
            transition_operation_status(
                db,
                operation=operation,
                to_status="failed",
                message=f"Telematics capture task failed: {exc}",
            )
        if retry_class == "non_retryable_intervention_required":
            if "org_id" in locals():
                mark_connection_intervention_required(
                    db,
                    org_id=_uuid.UUID(org_id),
                    provider="samsara",
                    domain="telematics",
                    reason_code=reason_code,
                    admin_action=_admin_action_for_reason(reason_code),
                    message=normalized_error.user_facing_message,
                )
            increment(MetricNames.CELERY_TASK_FAILURES)
            return {
                "incident_id": incident_id,
                "type": "telematics",
                "status": "failed",
                "reason_code": reason_code,
                "action_required": _admin_action_for_reason(reason_code),
                "idempotency_key": workflow_key,
            }
        policy = get_policy_for_capability("telematics")
        if self.request.retries < policy.max_retries:
            delay = compute_retry_delay_seconds(
                retry_count=self.request.retries,
                policy=policy,
            )
            raise self.retry(exc=exc, countdown=delay, max_retries=policy.max_retries)
        if "org_id" in locals():
            mark_connection_intervention_required(
                db,
                org_id=_uuid.UUID(org_id),
                provider="samsara",
                domain="telematics",
                reason_code="retry_ceiling_exceeded",
                admin_action="manual_investigation_required",
                message="Retry ceiling reached for telematics capture.",
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


# ---------------------------------------------------------------------------
# Task: capture_driver_violation_history (FMCSA MCMIS)
# ---------------------------------------------------------------------------


def _normalize_fmcsa_row(raw: dict) -> dict:
    """Translate a raw Socrata row into the columns used by ``fmcsa_inspections``."""
    insp_date = raw.get("insp_date") or raw.get("inspection_date_utc")
    parsed_date = _parse_iso(insp_date) if isinstance(insp_date, str) else insp_date

    unit_type = (raw.get("unit_type") or "").lower()
    if unit_type not in ("tractor", "trailer", "other"):
        unit_type = "other"

    violations = raw.get("violations") or raw.get("violations_json") or []

    return {
        "report_number": raw.get("report_number") or raw.get("report_num") or "",
        "inspection_date_utc": parsed_date,
        "report_state": raw.get("report_state"),
        "usdot_number": raw.get("dot_number") or raw.get("usdot_number") or "",
        "vehicle_vin": raw.get("vin") or raw.get("vehicle_vin"),
        "vehicle_license_plate": (
            raw.get("license_plate") or raw.get("vehicle_license_plate")
        ),
        "vehicle_license_state": (
            raw.get("license_state") or raw.get("vehicle_license_state")
        ),
        "unit_type": unit_type,
        "inspection_level": str(raw.get("inspection_level") or "") or None,
        "oos_total": int(raw.get("oos_total") or 0),
        "violation_count": int(raw.get("violation_count") or len(violations) or 0),
        "violations_json": violations,
        "raw_json": raw,
    }


@celery_app.task(
    bind=True,
    acks_late=True,
    name="app.tasks.evidence_tasks.capture_driver_violation_history",
    max_retries=3,
    soft_time_limit=180,
    time_limit=240,
)
def capture_driver_violation_history(
    self,
    operation_id: str,
    evidence_request_id: str,
    org_id: str,
    incident_id: str,
    adc_driver_id: str | None,
    usdot_number: str,
):
    """Pull FMCSA MCMIS inspections for the carrier, run slip-seating
    attribution against the driver's unit history, and persist the
    per-incident match rows.
    """
    from datetime import timedelta

    from app.core.config import settings as _settings
    from app.db.models import (
        Driver,
        EvidenceRequest,
        IntegrationOperation,
    )
    from app.db.repo.driver_unit_history import (
        derive_from_assignments,
        list_active_for_driver_in_window,
    )
    from app.db.repo.fmcsa_inspections import (
        create_snapshot,
        get_latest_succeeded_snapshot,
        is_snapshot_fresh,
        list_inspections_for_org,
        replace_incident_attributions,
        upsert_inspections,
    )
    from app.domain.system_event_types import SystemEventType
    from app.integrations.registry import get_provider
    from app.integrations.models import ProviderCapability
    from app.services.fmcsa_attribution import (
        InspectionRow,
        UnitHistoryRow,
        attribute_inspections,
    )
    from app.services.integration_health_service import (
        set_evidence_request_status,
        transition_operation_status,
    )

    increment("evidence.capture_inspections.attempts")
    inc_uuid = _uuid.UUID(incident_id)
    org_uuid = _uuid.UUID(org_id)
    op_uuid = _uuid.UUID(operation_id)
    er_uuid = _uuid.UUID(evidence_request_id)

    db = _get_db()

    try:
        operation = (
            db.query(IntegrationOperation)
            .filter(IntegrationOperation.operation_id == op_uuid)
            .first()
        )
        evidence_request = (
            db.query(EvidenceRequest)
            .filter(EvidenceRequest.evidence_request_id == er_uuid)
            .first()
        )
        if operation is None or evidence_request is None:
            return {
                "status": "missing_records",
                "operation_id": operation_id,
                "evidence_request_id": evidence_request_id,
            }

        transition_operation_status(
            db,
            operation=operation,
            to_status="running",
            message="FMCSA inspection capture task started",
        )

        # --- 1. Cache check ---
        ttl_hours = int(getattr(_settings, "FMCSA_CACHE_TTL_HOURS", 6))
        snapshot = get_latest_succeeded_snapshot(db, org_id=org_uuid)
        if snapshot is None or not is_snapshot_fresh(snapshot, ttl_hours=ttl_hours):
            now = datetime.now(timezone.utc)
            lookback_days = int(getattr(_settings, "FMCSA_LOOKBACK_DAYS", 360))
            window_start = now - timedelta(days=lookback_days)
            provider = get_provider(ProviderCapability.INSPECTIONS)
            try:
                raw_rows = list(
                    provider.fetch_inspections(
                        usdot_number=usdot_number,
                        since=window_start.date().isoformat(),
                        until=now.date().isoformat(),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                normalized = as_normalized_error(exc, provider_hint="fmcsa")
                from app.db.repo.evidence_requests import (
                    update_evidence_request_error,
                )
                from app.db.repo.integration_operations import (
                    update_integration_operation_error,
                )

                update_integration_operation_error(db, operation, normalized)
                update_evidence_request_error(db, evidence_request, normalized)
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.EVIDENCE_CAPTURE_FAILED,
                    {
                        "type": "inspections",
                        "operation_id": operation_id,
                        "error": normalized.code,
                    },
                )
                set_evidence_request_status(
                    db, evidence_request=evidence_request, status="failed"
                )
                transition_operation_status(
                    db,
                    operation=operation,
                    to_status="failed",
                    message=normalized.operator_message,
                )
                return {"status": "failed", "error": normalized.code}

            normalized_rows = [_normalize_fmcsa_row(r) for r in raw_rows]
            snapshot = create_snapshot(
                db,
                org_id=org_uuid,
                usdot_number=usdot_number,
                window_start_utc=window_start,
                window_end_utc=now,
                record_count=len(normalized_rows),
                status="succeeded",
            )
            upsert_inspections(db, snapshot=snapshot, rows=normalized_rows)

        # --- 2. Build driver unit set ---
        driver_id = None
        if adc_driver_id:
            driver = (
                db.query(Driver)
                .filter(
                    Driver.org_id == org_uuid,
                    Driver.driver_id == adc_driver_id,
                )
                .first()
                if _is_uuid_string(adc_driver_id)
                else None
            )
            if driver is not None:
                driver_id = driver.driver_id

        lookback_days = int(getattr(_settings, "FMCSA_LOOKBACK_DAYS", 360))
        window_start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        if driver_id is not None:
            unit_rows = list_active_for_driver_in_window(
                db,
                org_id=org_uuid,
                driver_id=driver_id,
                window_start_utc=window_start,
            )
            if not unit_rows:
                unit_rows = derive_from_assignments(
                    db, org_id=org_uuid, driver_id=driver_id
                )
        else:
            unit_rows = []

        # --- 3. Match ---
        inspections_db = list_inspections_for_org(
            db, org_id=org_uuid, since_utc=window_start
        )
        inspection_rows = [
            InspectionRow(
                inspection_id=str(i.inspection_id),
                inspection_date_utc=i.inspection_date_utc,
                vehicle_vin=i.vehicle_vin,
                vehicle_license_plate=i.vehicle_license_plate,
                vehicle_license_state=i.vehicle_license_state,
            )
            for i in inspections_db
        ]
        unit_history_rows = [
            UnitHistoryRow(
                history_id=str(u.id),
                unit_kind=u.unit_kind,
                vin=u.vin,
                license_plate=u.license_plate,
                license_state=u.license_state,
                started_at_utc=u.started_at_utc,
                ended_at_utc=u.ended_at_utc,
                confidence=u.confidence,
            )
            for u in unit_rows
        ]
        matches = attribute_inspections(
            inspections=inspection_rows, unit_history=unit_history_rows
        )

        # --- 4. Persist matches ---
        match_payload = []
        for m in matches:
            match_payload.append(
                {
                    "inspection_id": _uuid.UUID(m.inspection_id),
                    "unit_history_id": (
                        _uuid.UUID(m.unit_history_id) if m.unit_history_id else None
                    ),
                    "driver_id": driver_id,
                    "match_basis": m.match_basis,
                    "match_confidence": m.match_confidence,
                    "included_in_brief": m.included_in_brief,
                    "excluded_reason": m.excluded_reason,
                }
            )
        # Only persist matches whose inspection actually exists in the snapshot
        valid_ids = {str(i.inspection_id) for i in inspections_db}
        match_payload = [
            mp for mp in match_payload if str(mp["inspection_id"]) in valid_ids
        ]
        replace_incident_attributions(
            db, incident_id=inc_uuid, matches=match_payload
        )

        included = sum(1 for m in matches if m.included_in_brief)
        low = sum(1 for m in matches if m.match_confidence == "low")

        _emit(
            db,
            inc_uuid,
            SystemEventType.MCMIS_INSPECTIONS_FETCHED,
            {
                "operation_id": operation_id,
                "usdot_number": usdot_number,
                "snapshot_record_count": snapshot.record_count if snapshot else 0,
                "match_total": len(matches),
                "match_included": included,
                "match_low_confidence": low,
            },
        )
        _emit(
            db,
            inc_uuid,
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED,
            {"type": "inspections", "operation_id": operation_id},
        )
        set_evidence_request_status(
            db, evidence_request=evidence_request, status="fulfilled"
        )
        transition_operation_status(
            db,
            operation=operation,
            to_status="succeeded",
            message="FMCSA inspections captured",
        )

        return {
            "status": "ok",
            "incident_id": incident_id,
            "match_total": len(matches),
            "match_included": included,
            "match_low_confidence": low,
        }
    finally:
        db.close()


def _is_uuid_string(value: str | None) -> bool:
    if not value:
        return False
    try:
        _uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
