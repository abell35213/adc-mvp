"""Export API routes."""

import uuid
import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.error_responses import raise_api_error
from app.api.schemas import (
    CreateExportEnqueueResponse,
    CreateExportRequest,
    DownloadExportResponse,
    ExportDownloadAuditResponse,
    ExportContentsResponse,
    ExportStatusResponse,
    ExportSummary,
    RetryExportRequest,
)
from app.audit.emitter import emit_audit_event
from app.core.deps import get_current_user
from app.core.logging import set_log_context
from app.core.metrics import MetricNames, increment, timed
from app.db.models import User
from app.db.session import get_db
from app.db.repo.exports import (
    create_export,
    get_export,
    get_exports_by_incident,
    list_exports_for_org_ids,
    update_export,
)
from app.db.repo.artifacts import get_artifacts_by_incident
from app.db.repo.events import create_event, get_events_by_incident
from app.db.repo.incidents import get_incident
from app.domain.system_event_types import SystemEventType
from app.core.config import settings
from app.tasks.export_tasks import build_export
from app.services.idempotency_service import optional_idempotency_key, find_event_by_idempotency
from app.services.rate_limit_service import enforce_rate_limit
from app.domain.packet_profiles import get_default_packet_profile
from app.security.authn import UserAuthContext, build_user_auth_context
from app.security.authz import can_download_export, can_request_export, require_policy
from app.services.vault_s3 import (
    S3PresignConfigurationError,
    S3PresignGenerationError,
    generate_presigned_download_url,
)

logger = logging.getLogger(__name__)

router = APIRouter()
STABLE_EXPORT_CONTENT_KINDS: tuple[str, ...] = ("summary_pdf", "raw_telemetry", "photo")


@router.post("/", response_model=CreateExportEnqueueResponse, status_code=201)
def create_export_endpoint(
    body: CreateExportRequest,
    request: Request,
    idempotency=Depends(optional_idempotency_key),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    increment(MetricNames.EXPORT_REQUEST_ATTEMPTS)
    enforce_rate_limit(
        request,
        bucket_name="export_request",
        subject=str(current_user.id),
        max_calls=settings.EXPORT_REQUEST_RATE_LIMIT,
        window_seconds=settings.EXPORT_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many export requests. Please retry later.",
    )

    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, body.incident_id)
    if incident is None:
        increment(MetricNames.EXPORT_REQUEST_FAILURES)
        raise_api_error(
            status_code=404,
            message="Incident not found",
            code="RESOURCE_NOT_FOUND",
        )
    allowed = can_request_export(context, incident)
    if not allowed:
        emit_audit_event(
            db,
            org_id=incident.org_id if incident else None,
            actor_type="user",
            actor_id=str(current_user.id),
            action="export.request",
            event_type="authorization_failed",
            outcome="failure",
            incident_id=body.incident_id,
            metadata={"should_log": True, "resource": "export_request"},
        )
    require_policy(allowed)
    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="export.request",
        event_type="export_requested",
        outcome="success",
        incident_id=incident.incident_id,
        metadata={"export_type": body.export_type},
    )

    set_log_context(
        user_id=str(current_user.id),
        org_id=str(incident.org_id) if incident.org_id else None,
    )

    if idempotency is not None:
        existing_event = find_event_by_idempotency(
            db,
            event_type=SystemEventType.EXPORT_REQUESTED.value,
            actor_type="user",
            actor_id=str(current_user.id),
            incident_id=body.incident_id,
            idempotency_key_hash=idempotency.hashed_key,
        )
        if existing_event and (existing_event.payload or {}).get("export_id"):
            prior = get_export(db, uuid.UUID(str(existing_event.payload["export_id"])))
            if prior is not None:
                return CreateExportEnqueueResponse(
                    export_id=prior.export_id,
                    incident_id=prior.incident_id,
                    export_type=prior.export_type,
                    status=prior.status,
                    created_at_utc=prior.created_at_utc,
                )

    export = create_export(
        db,
        incident_id=body.incident_id,
        org_id=incident.org_id,
        status="requested",
        export_type=body.export_type,
        profile_id=str(body.options_json.get("profile_id") or get_default_packet_profile(body.export_type).profile_id),
        requested_by_user_id=current_user.id,
        options_json=body.options_json,
        progress_stage="request_accepted",
    )

    create_event(
        db,
        incident_id=body.incident_id,
        event_type=SystemEventType.EXPORT_REQUESTED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload={
            "export_id": str(export.export_id),
            "incident_id": str(body.incident_id),
            "export_type": body.export_type,
            "status": "requested",
            "actor": {"type": "user", "id": str(current_user.id)},
            "idempotency_key_hash": idempotency.hashed_key if idempotency else None,
        },
    )

    try:
        task_result = build_export.delay(
            str(body.incident_id),
            str(export.export_id),
            {"attempt_number": 1, "trigger": "api"},
        )
    except Exception as exc:
        increment(MetricNames.EXPORT_REQUEST_FAILURES)
        logger.exception("Failed to enqueue export task")
        raise_api_error(
            status_code=502,
            message="Export processing is temporarily degraded.",
            code="THIRD_PARTY_DEGRADED",
            retry_hint="Please retry export generation in a few minutes.",
        )

    export = update_export(db, export.export_id, status="queued", transition_actor="api_user") or export
    task_id = getattr(task_result, "id", None)
    create_event(
        db,
        incident_id=body.incident_id,
        event_type=SystemEventType.EXPORT_QUEUED,
        actor_type="system",
        actor_id="api",
        payload={
            "export_id": str(export.export_id),
            "incident_id": str(body.incident_id),
            "export_type": export.export_type,
            "status": "queued",
            "task_id": str(task_id) if isinstance(task_id, (str, uuid.UUID)) else None,
            "attempt_number": 1,
            "actor": {"type": "system", "id": "api"},
        },
    )

    return CreateExportEnqueueResponse(
        export_id=export.export_id,
        incident_id=export.incident_id,
        export_type=export.export_type,
        status=export.status,
        created_at_utc=export.created_at_utc,
    )


@router.post("/{export_id}/retry", response_model=CreateExportEnqueueResponse, status_code=201)
def retry_export_endpoint(
    export_id: uuid.UUID,
    body: RetryExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    failed_export = _resolve_authorized_export(db, export_id, list(context.org_ids), context=context)
    if failed_export.status != "failed":
        raise_api_error(
            status_code=409,
            message="Only failed exports can be retried.",
            code="EXPORT_RETRY_ALLOWED",
            retry_hint="Wait for the export to fail, then retry.",
        )

    new_export = create_export(
        db,
        incident_id=failed_export.incident_id,
        org_id=failed_export.org_id,
        status="requested",
        export_type=body.export_type or failed_export.export_type,
        profile_id=(
            str((body.options_json or {}).get("profile_id"))
            if body.options_json and body.options_json.get("profile_id")
            else (
                get_default_packet_profile(body.export_type).profile_id
                if body.export_type and body.export_type != failed_export.export_type
                else failed_export.profile_id
            )
        ),
        requested_by_user_id=current_user.id,
        retry_parent_export_id=failed_export.export_id,
        options_json=body.options_json
        if body.options_json is not None
        else (failed_export.options_json or {}),
        progress_stage="request_accepted",
    )

    attempt_number = _get_retry_attempt_number(db, new_export)
    emit_audit_event(
        db,
        org_id=failed_export.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="export.retry_request",
        event_type="export_requested",
        outcome="success",
        incident_id=failed_export.incident_id,
        export_id=new_export.export_id,
        metadata={"prior_export_id": str(failed_export.export_id), "attempt_number": attempt_number},
    )
    create_event(
        db,
        incident_id=failed_export.incident_id,
        event_type=SystemEventType.EXPORT_RETRY_REQUESTED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload={
            "export_id": str(new_export.export_id),
            "prior_export_id": str(failed_export.export_id),
            "incident_id": str(failed_export.incident_id),
            "export_type": new_export.export_type,
            "status": "requested",
            "attempt_number": attempt_number,
            "actor": {"type": "user", "id": str(current_user.id)},
        },
    )

    try:
        task_result = build_export.delay(
            str(failed_export.incident_id),
            str(new_export.export_id),
            {"attempt_number": attempt_number, "trigger": "retry_api"},
        )
    except Exception as exc:
        logger.exception("Failed to enqueue retry export task")
        raise_api_error(
            status_code=502,
            message="Export processing is temporarily degraded.",
            code="THIRD_PARTY_DEGRADED",
            retry_hint="Please retry export generation in a few minutes.",
        )
    new_export = update_export(db, new_export.export_id, status="queued", transition_actor="api_user") or new_export
    task_id = getattr(task_result, "id", None)
    create_event(
        db,
        incident_id=failed_export.incident_id,
        event_type=SystemEventType.EXPORT_QUEUED,
        actor_type="system",
        actor_id="api",
        payload={
            "export_id": str(new_export.export_id),
            "incident_id": str(failed_export.incident_id),
            "export_type": new_export.export_type,
            "status": "queued",
            "task_id": str(task_id) if isinstance(task_id, (str, uuid.UUID)) else None,
            "attempt_number": attempt_number,
            "actor": {"type": "system", "id": "api"},
        },
    )
    return CreateExportEnqueueResponse(
        export_id=new_export.export_id,
        incident_id=new_export.incident_id,
        export_type=new_export.export_type,
        status=new_export.status,
        created_at_utc=new_export.created_at_utc,
    )


def _get_export_owner_org_id(db: Session, export):
    """Resolve org ownership for an export, including legacy null-org rows."""
    if export.org_id is not None:
        return export.org_id

    incident = get_incident(db, export.incident_id)
    if incident is None:
        return None
    return incident.org_id


def _serialize_export(export):
    return {
        "export_id": str(export.export_id),
        "incident_id": str(export.incident_id),
        "export_type": export.export_type,
        "profile_id": export.profile_id,
        "requested_by_user_id": (
            str(export.requested_by_user_id) if export.requested_by_user_id else None
        ),
        "retry_parent_export_id": (
            str(export.retry_parent_export_id) if export.retry_parent_export_id else None
        ),
        "options_json": export.options_json or {},
        "status": export.status,
        "progress_stage": export.progress_stage,
        "error_message": export.error_message,
        "package_sha256": export.package_sha256,
        "byte_size": export.byte_size,
        "artifact_count": export.artifact_count,
        "timeline_event_count": export.timeline_event_count,
        "requested_at_utc": export.requested_at_utc,
        "processing_started_at_utc": export.processing_started_at_utc,
        "completed_at_utc": export.completed_at_utc,
        "expires_at_utc": export.expires_at_utc,
        "created_at_utc": export.created_at_utc,
        "updated_at_utc": export.updated_at_utc,
    }


def _resolve_authorized_export(
    db: Session,
    export_id: uuid.UUID,
    org_ids: list[uuid.UUID],
    context: UserAuthContext | None = None,
):
    export = get_export(db, export_id)
    if not export:
        raise_api_error(
            status_code=404,
            message="Export not found",
            code="RESOURCE_NOT_FOUND",
        )

    export_org_id = _get_export_owner_org_id(db, export)
    if context is not None:
        if not can_download_export(context, export, export_org_id=export_org_id):
            emit_audit_event(
                db,
                org_id=export_org_id,
                actor_type="user",
                actor_id=str(context.user.id),
                action="export.authorize",
                event_type="authorization_failed",
                outcome="failure",
                incident_id=export.incident_id,
                export_id=export.export_id,
                metadata={"should_log": True, "resource": "export"},
            )
            require_policy(False)
    elif export_org_id is None or export_org_id not in org_ids:
        raise_api_error(
            status_code=403,
            message="You do not have access to this export.",
            code="ACCESS_DENIED",
        )
    return export


def _get_retry_attempt_number(db: Session, retry_export) -> int:
    chain_exports = get_exports_by_incident(db, retry_export.incident_id)
    by_id = {item.export_id: item for item in chain_exports}
    root_id = retry_export.export_id
    cursor = retry_export
    while cursor.retry_parent_export_id and cursor.retry_parent_export_id in by_id:
        root_id = cursor.retry_parent_export_id
        cursor = by_id[cursor.retry_parent_export_id]

    attempts = 0
    for item in chain_exports:
        candidate = item
        while candidate.retry_parent_export_id and candidate.retry_parent_export_id in by_id:
            candidate = by_id[candidate.retry_parent_export_id]
        if candidate.export_id == root_id:
            attempts += 1
    return attempts


def _is_presigned_https_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.netloc or "").lower()
    query = parse_qs(parsed.query)
    has_signature = any(
        token in query
        for token in (
            "X-Amz-Signature",
            "x-amz-signature",
            "Signature",
            "signature",
        )
    )
    if has_signature:
        return True
    return "amazonaws.com" not in host


def _normalize_manifest_rows(rows) -> list[dict]:
    normalized: dict[str, dict] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        if not isinstance(kind, str):
            continue
        byte_size = row.get("byte_size")
        normalized[str(kind)] = {
            "kind": kind,
            "item": row.get("item"),
            "path": row.get("path"),
            "classification": row.get("classification") or ("included" if row.get("included") else "unavailable"),
            "included": bool(row.get("included", False)),
            "reason": row.get("reason"),
            "byte_size": byte_size if isinstance(byte_size, int) and byte_size >= 0 else None,
        }
    if normalized:
        return list(normalized.values())
    return [
        {
            "kind": kind,
            "item": kind,
            "path": None,
            "classification": "unavailable",
            "included": False,
            "reason": "not_recorded",
            "byte_size": None,
        }
        for kind in STABLE_EXPORT_CONTENT_KINDS
    ]


def _reconstruct_manifest(db: Session, export) -> list[dict]:
    artifacts = get_artifacts_by_incident(db, export.incident_id)
    has_captured_photos = any(
        a.status == "captured" and (a.artifact_type or "").lower() == "photo"
        for a in artifacts
    )
    raw_telemetry_bytes = sum(
        int(a.byte_size)
        for a in artifacts
        if a.status == "captured"
        and (a.artifact_type or "").lower() in {"eld_log", "gps_trail", "safety_event", "vehicle_state"}
        and isinstance(a.byte_size, int)
        and a.byte_size >= 0
    )

    return [
        {
            "kind": "summary_pdf",
            "item": "00_Cover_Summary.pdf",
            "path": None,
            "classification": "included" if export.status in {"ready", "processing", "failed"} else "unavailable",
            "included": export.status in {"ready", "processing", "failed"},
            "reason": None,
            "byte_size": None,
        },
        {
            "kind": "raw_telemetry",
            "item": "raw_telemetry",
            "path": None,
            "classification": "included" if raw_telemetry_bytes > 0 else "unavailable",
            "included": raw_telemetry_bytes > 0,
            "reason": None if raw_telemetry_bytes > 0 else "no_captured_telemetry",
            "byte_size": raw_telemetry_bytes or None,
        },
        {
            "kind": "photo",
            "item": "photo",
            "path": None,
            "classification": "included" if has_captured_photos else "unavailable",
            "included": has_captured_photos,
            "reason": None if has_captured_photos else "no_captured_photos",
            "byte_size": sum(
                int(a.byte_size)
                for a in artifacts
                if a.status == "captured"
                and (a.artifact_type or "").lower() == "photo"
                and isinstance(a.byte_size, int)
                and a.byte_size >= 0
            )
            or None,
        },
    ]


def _build_contents_manifest(db: Session, export) -> list[dict]:
    options = export.options_json or {}
    manifest_rows = options.get("file_manifest") if isinstance(options, dict) else None
    if not isinstance(manifest_rows, list):
        manifest_rows = options.get("contents_manifest") if isinstance(options, dict) else None
    if isinstance(manifest_rows, list):
        normalized = _normalize_manifest_rows(manifest_rows)
        if normalized:
            return normalized
    return _reconstruct_manifest(db, export)


@router.get("/", response_model=list[ExportSummary])
def list_exports_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )
    exports = list_exports_for_org_ids(db, org_ids)
    return [_serialize_export(export) for export in exports]


@router.get("/{export_id}", response_model=ExportSummary)
def get_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )
    try:
        export = _resolve_authorized_export(db, export_id, org_ids, context=context)
    except HTTPException:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise

    return _serialize_export(export)


@router.get("/{export_id}/status", response_model=ExportStatusResponse)
def get_export_status_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    export = _resolve_authorized_export(db, export_id, org_ids, context=context)
    return ExportStatusResponse(
        status=export.status,
        progress_stage=export.progress_stage,
        error_message=export.error_message,
    )


@router.get("/{export_id}/contents", response_model=ExportContentsResponse)
def get_export_contents_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    export = _resolve_authorized_export(db, export_id, org_ids, context=context)
    emit_audit_event(
        db,
        org_id=_get_export_owner_org_id(db, export),
        actor_type="user",
        actor_id=str(current_user.id),
        action="export.contents.retrieve",
        event_type="export_retrieved",
        outcome="success",
        incident_id=export.incident_id,
        export_id=export.export_id,
    )
    manifest = _build_contents_manifest(db, export)
    options = export.options_json or {}
    missing_items = options.get("missing_items") if isinstance(options, dict) else []
    warnings = options.get("warnings") if isinstance(options, dict) else []
    return ExportContentsResponse(
        export_id=export.export_id,
        status=export.status,
        progress_stage=export.progress_stage,
        file_manifest=manifest,
        missing_items=missing_items if isinstance(missing_items, list) else [],
        warnings=warnings if isinstance(warnings, list) else [],
    )


@router.get("/{export_id}/download", response_model=DownloadExportResponse)
def download_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    increment(MetricNames.EXPORT_DOWNLOAD_ATTEMPTS)
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    with timed(MetricNames.EXPORT_DOWNLOAD_ATTEMPTS):
        set_log_context(
            user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
        )
        export = get_export(db, export_id)
    if not export:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise_api_error(
            status_code=404,
            message="Export not found",
            code="RESOURCE_NOT_FOUND",
        )

    export_org_id = _get_export_owner_org_id(db, export)
    if not can_download_export(context, export, export_org_id=export_org_id):
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        emit_audit_event(
            db,
            org_id=export_org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="export.download",
            event_type="authorization_failed",
            outcome="failure",
            incident_id=export.incident_id,
            export_id=export.export_id,
            metadata={"should_log": True, "resource": "export_download"},
        )
        raise_api_error(
            status_code=403,
            message="You do not have access to this export.",
            code="ACCESS_DENIED",
        )

    if export.status != "ready":
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise_api_error(
            status_code=409,
            message="Export is still processing.",
            code="EXPORT_DELAYED",
            retry_hint="Try downloading again in 30-60 seconds.",
        )
    now = datetime.now(timezone.utc)
    expires_at = export.expires_at_utc
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise_api_error(
            status_code=410,
            message="This export link has expired.",
            code="EXPORT_EXPIRED",
            retry_hint="Generate a new export package and retry download.",
        )

    bucket = export.s3_bucket or settings.S3_BUCKET
    key = export.s3_key or f"exports/{export.export_id}.zip"
    expires_in_seconds = settings.EXPORT_DOWNLOAD_URL_EXPIRES_SECONDS

    try:
        presigned_url = generate_presigned_download_url(
            bucket=bucket,
            key=key,
            region=settings.AWS_REGION,
            expires_in=expires_in_seconds,
        )
    except S3PresignConfigurationError as exc:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        logger.warning("Presign configuration invalid", extra={"error": str(exc)})
        raise_api_error(
            status_code=422,
            message="Export download is temporarily unavailable.",
            code="THIRD_PARTY_DEGRADED",
            retry_hint="Please retry shortly or contact support with the correlation ID.",
        )
    except S3PresignGenerationError as exc:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise_api_error(
            status_code=502,
            message="Unable to prepare export download right now.",
            code="THIRD_PARTY_DEGRADED",
            retry_hint="Please retry in a few minutes.",
        )
    if not _is_presigned_https_url(presigned_url):
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise_api_error(
            status_code=502,
            message="Unable to prepare export download right now.",
            code="THIRD_PARTY_DEGRADED",
            retry_hint="Please retry in a few minutes.",
        )

    create_event(
        db,
        incident_id=export.incident_id,
        event_type=SystemEventType.EXPORT_DOWNLOADED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload={
            "export_id": str(export.export_id),
            "incident_id": str(export.incident_id),
            "export_type": export.export_type,
            "status": "ready",
            "download_url_expires_in_seconds": expires_in_seconds,
            "downloaded_at_utc": now.isoformat(),
            "actor": {"type": "user", "id": str(current_user.id)},
        },
    )
    emit_audit_event(
        db,
        org_id=export_org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="export.download",
        event_type="export_downloaded",
        outcome="success",
        incident_id=export.incident_id,
        export_id=export.export_id,
        metadata={"download_url_expires_in_seconds": expires_in_seconds},
    )

    return DownloadExportResponse(
        export_id=export.export_id,
        url=presigned_url,
        status="ready",
        progress_stage="ready_for_download",
    )


@router.get("/{export_id}/downloads", response_model=ExportDownloadAuditResponse)
def get_export_downloads_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    export = _resolve_authorized_export(db, export_id, org_ids, context=context)
    emit_audit_event(
        db,
        org_id=_get_export_owner_org_id(db, export),
        actor_type="user",
        actor_id=str(current_user.id),
        action="export.download_audit.retrieve",
        event_type="export_retrieved",
        outcome="success",
        incident_id=export.incident_id,
        export_id=export.export_id,
    )
    events = get_events_by_incident(db, export.incident_id)
    download_events = [
        event
        for event in events
        if event.event_type == SystemEventType.EXPORT_DOWNLOADED
        and isinstance(event.payload, dict)
        and event.payload.get("export_id") == str(export.export_id)
    ]
    ordered_events = sorted(download_events, key=lambda event: event.occurred_at_utc or "")
    return ExportDownloadAuditResponse(
        export_id=export.export_id,
        downloads=[
            {
                "event_type": event.event_type,
                "occurred_at_utc": event.occurred_at_utc,
                "actor_type": event.actor_type,
                "payload": event.payload,
            }
            for event in ordered_events
        ],
    )
