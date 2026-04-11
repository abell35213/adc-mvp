"""Incident API routes."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    ArtifactSummary,
    CreateExportResponse,
    CreateIncidentRequest,
    CreateIncidentResponse,
    EventSummary,
    ExportSummary,
    IncidentDetailResponse,
    IncidentListItem,
)
from app.core.deps import get_current_user
from app.core.logging import get_request_id, set_log_context
from app.core.metrics import MetricNames, increment, timed
from app.db.models import User
from app.db.repo.artifacts import get_artifacts_by_incident
from app.db.repo.events import create_event, get_events_by_incident
from app.db.repo.exports import create_export, get_exports_by_incident
from app.db.repo.incidents import create_incident, get_incident, list_incidents
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.domain.packet_profiles import get_default_packet_profile
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics_bundle
from app.tasks.export_tasks import build_export
from app.services.idempotency_service import optional_idempotency_key, find_event_by_idempotency
from app.services.rate_limit_service import enforce_rate_limit
from app.core.config import settings
from app.security.authn import build_user_auth_context
from app.security.authz import (
    can_create_incident,
    can_request_export,
    can_view_incident,
    require_policy,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[IncidentListItem])
def list_incidents_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )
    incidents = list_incidents(db, org_ids=org_ids)
    result = []
    for inc in incidents:
        artifacts = get_artifacts_by_incident(db, inc.incident_id)
        captured = sum(1 for a in artifacts if a.status == "captured")
        result.append(
            IncidentListItem(
                incident_id=inc.incident_id,
                status=inc.status,
                severity=inc.severity,
                adc_vehicle_id=inc.adc_vehicle_id,
                samsara_vehicle_id=inc.samsara_vehicle_id,
                adc_driver_id=inc.adc_driver_id,
                created_at_utc=inc.created_at_utc.isoformat()
                if inc.created_at_utc
                else None,
                evidence_captured=captured,
                evidence_total=len(artifacts),
            )
        )
    return result


@router.post("/", response_model=CreateIncidentResponse, status_code=201)
def create_incident_endpoint(
    body: CreateIncidentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    increment(MetricNames.INCIDENT_CREATE_ATTEMPTS)

    with timed(MetricNames.INCIDENT_CREATE_ATTEMPTS):
        context = build_user_auth_context(db, current_user)
        require_policy(can_create_incident(context))
        org_id = context.org_ids[0]
        set_log_context(
            user_id=str(current_user.id), org_id=str(org_id) if org_id else None
        )

        incident = create_incident(
            db,
            status="evidence_capturing",
            adc_vehicle_id=body.adc_vehicle_id,
            samsara_vehicle_id=body.samsara_vehicle_id,
            adc_driver_id=body.adc_driver_id,
            severity=body.severity,
            org_id=org_id,
        )

        incident_id = incident.incident_id

        create_event(
            db,
            incident_id=incident_id,
            event_type=SystemEventType.INCIDENT_STARTED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload={
                "severity": body.severity,
                "adc_vehicle_id": body.adc_vehicle_id,
                "samsara_vehicle_id": body.samsara_vehicle_id,
                "adc_driver_id": body.adc_driver_id,
            },
        )

        create_event(
            db,
            incident_id=incident_id,
            event_type=SystemEventType.EVIDENCE_LOCKDOWN_STARTED,
            actor_type="user",
            actor_id=str(current_user.id),
        )

        window_start = body.window_start or ""
        window_end = body.window_end or ""
        str_id = str(incident_id)

        logger.info("Queueing evidence capture tasks", extra={"request_id": get_request_id()})
        capture_dashcam.delay(str_id, window_start, window_end)
        capture_telematics_bundle.delay(str_id, window_start, window_end)

    return CreateIncidentResponse(
        incident_id=incident_id,
        status=incident.status,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident_endpoint(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )

    incident = get_incident(db, incident_id, org_ids=org_ids)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_view_incident(context, incident))

    artifacts = get_artifacts_by_incident(db, incident_id)
    exports = get_exports_by_incident(db, incident_id)
    events = get_events_by_incident(db, incident_id)

    return IncidentDetailResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        severity=incident.severity,
        adc_vehicle_id=incident.adc_vehicle_id,
        samsara_vehicle_id=incident.samsara_vehicle_id,
        adc_driver_id=incident.adc_driver_id,
        created_at_utc=incident.created_at_utc.isoformat()
        if incident.created_at_utc
        else None,
        evidence_inventory=[
            ArtifactSummary(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type,
                status=a.status,
                captured_at_utc=(
                    a.capture_window_end_utc.isoformat()
                    if a.capture_window_end_utc
                    else None
                ),
                unavailable_reason=a.unavailable_reason_code,
                unavailable_message=a.unavailable_reason_detail,
            )
            for a in artifacts
        ],
        export_status=[
            ExportSummary(
                export_id=e.export_id,
                incident_id=e.incident_id,
                export_type=e.export_type,
                profile_id=e.profile_id,
                requested_by_user_id=e.requested_by_user_id,
                options_json=e.options_json or {},
                status=e.status,
                progress_stage=e.progress_stage,
                error_message=e.error_message,
                package_sha256=e.package_sha256,
                byte_size=e.byte_size,
                artifact_count=e.artifact_count,
                timeline_event_count=e.timeline_event_count,
                requested_at_utc=e.requested_at_utc.isoformat()
                if e.requested_at_utc
                else None,
                processing_started_at_utc=e.processing_started_at_utc.isoformat()
                if e.processing_started_at_utc
                else None,
                completed_at_utc=e.completed_at_utc.isoformat()
                if e.completed_at_utc
                else None,
                expires_at_utc=e.expires_at_utc.isoformat() if e.expires_at_utc else None,
                created_at_utc=e.created_at_utc.isoformat() if e.created_at_utc else None,
                updated_at_utc=e.updated_at_utc.isoformat() if e.updated_at_utc else None,
            )
            for e in exports
        ],
        timeline=[
            EventSummary(
                event_type=ev.event_type,
                occurred_at_utc=ev.occurred_at_utc.isoformat()
                if ev.occurred_at_utc
                else "",
                actor_type=ev.actor_type,
                payload=ev.payload,
            )
            for ev in sorted(events, key=lambda e: e.occurred_at_utc or "")
        ],
    )


@router.post(
    "/{incident_id}/exports", response_model=CreateExportResponse, status_code=201
)
def request_export_endpoint(
    incident_id: uuid.UUID,
    request: Request,
    idempotency=Depends(optional_idempotency_key),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    increment(MetricNames.EXPORT_REQUEST_ATTEMPTS)
    enforce_rate_limit(
        request,
        bucket_name="incident_export_request",
        subject=str(current_user.id),
        max_calls=settings.EXPORT_REQUEST_RATE_LIMIT,
        window_seconds=settings.EXPORT_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many export requests. Please retry later.",
    )

    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    incident = get_incident(db, incident_id, org_ids=org_ids)
    if not incident:
        increment(MetricNames.EXPORT_REQUEST_FAILURES)
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_request_export(context, incident))

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
            incident_id=incident_id,
            idempotency_key_hash=idempotency.hashed_key,
        )
        if existing_event and (existing_event.payload or {}).get("export_id"):
            prior_export_id = uuid.UUID(str(existing_event.payload["export_id"]))
            prior_export = get_exports_by_incident(db, incident_id)
            for row in prior_export:
                if row.export_id == prior_export_id:
                    return CreateExportResponse(
                        export_id=row.export_id,
                        status=row.status,
                        progress_stage=row.progress_stage,
                    )

    export = create_export(
        db,
        incident_id=incident_id,
        org_id=incident.org_id,
        status="requested",
        export_type="court_defense",
        profile_id=get_default_packet_profile("court_defense").profile_id,
        requested_by_user_id=current_user.id,
        progress_stage="request_accepted",
    )

    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.EXPORT_REQUESTED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload={
            "export_id": str(export.export_id),
            "incident_id": str(incident_id),
            "export_type": "court_defense",
            "status": "requested",
            "actor": {"type": "user", "id": str(current_user.id)},
        },
    )

    logger.info("Queueing export build task", extra={"request_id": get_request_id()})
    task_result = build_export.delay(str(incident_id), str(export.export_id))
    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.EXPORT_QUEUED,
        actor_type="system",
        actor_id="api",
        payload={
            "export_id": str(export.export_id),
            "incident_id": str(incident_id),
            "export_type": "court_defense",
            "status": "queued",
            "task_id": str(getattr(task_result, "id", "") or ""),
            "attempt_number": 1,
            "actor": {"type": "system", "id": "api"},
        },
    )

    return CreateExportResponse(export_id=export.export_id, status=export.status, progress_stage=export.progress_stage)
