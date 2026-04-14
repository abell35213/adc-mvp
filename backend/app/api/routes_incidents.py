"""Incident API routes."""

import logging
import uuid
from datetime import datetime, timezone

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
    IncidentOwnerPatchRequest,
    IncidentOwnerPatchResponse,
    IncidentStatusPatchRequest,
    IncidentStatusPatchResponse,
)
from app.audit.emitter import emit_audit_event
from app.core.deps import get_current_user
from app.core.logging import get_request_id, set_log_context
from app.core.metrics import MetricNames, increment, timed
from app.case_ops.service import build_case_snapshot, validate_case_status_transition
from app.db.models import User
from app.db.repo.artifacts import get_artifacts_by_incident
from app.db.repo.events import create_event, get_events_by_incident
from app.db.repo.exports import create_export, get_exports_by_incident
from app.db.repo.incidents import create_incident, get_incident, list_incidents
from app.db.repo.message_operations import get_messaging_reliability_summary
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.domain.packet_profiles import get_default_packet_profile
from app.tasks.export_tasks import build_export
from app.services.idempotency_service import (
    optional_idempotency_key,
    find_event_by_idempotency,
)
from app.services.incident_evidence_orchestrator import IncidentEvidenceOrchestrator
from app.services.dashcam_reason_codes import dashcam_reason_message
from app.services.rate_limit_service import enforce_rate_limit
from app.services.incident_ownership_service import patch_incident_owner
from app.core.config import settings
from app.security.authn import build_user_auth_context
from app.security.authz import (
    can_create_incident,
    can_modify_incident,
    can_request_export,
    can_view_incident,
    require_policy,
)
from app.security.permissions import Capability, has_capability

logger = logging.getLogger(__name__)

router = APIRouter()


def _required_transition_capability(
    from_status: str, to_status: str
) -> Capability | None:
    if to_status == "closed":
        return Capability.INCIDENT_CLOSE
    if from_status == "closed" and to_status == "in_review":
        return Capability.INCIDENT_REOPEN
    if to_status == "escalated":
        return Capability.INCIDENT_ESCALATE
    return None


def _event_context_payload(
    *,
    actor_id: uuid.UUID,
    incident_id: uuid.UUID,
    org_id: uuid.UUID | None,
    reason: str | None,
    previous: dict[str, str | None],
    new: dict[str, str | None],
) -> dict[str, object]:
    return {
        "actor": {"type": "user", "id": str(actor_id)},
        "incident_id": str(incident_id),
        "org_id": str(org_id) if org_id else None,
        "reason": reason,
        "previous": previous,
        "new": new,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


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
        snapshot = build_case_snapshot(
            incident=inc,
            artifacts=artifacts,
            events=[],
            exports=[],
        )
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
                completeness_percent=snapshot.completeness.percent,
                completeness_status=snapshot.completeness.status,
                readiness_state=snapshot.readiness.state,
                blocker_counts={
                    "critical": snapshot.blockers.critical_count,
                    "important": snapshot.blockers.important_count,
                    "optional": snapshot.blockers.optional_count,
                },
            )
        )
    return result


@router.post("/", response_model=CreateIncidentResponse, status_code=201)
def create_incident_endpoint(
    body: CreateIncidentRequest,
    request: Request,
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

        window_start = body.window_start
        window_end = body.window_end
        request_correlation_id = (
            request.headers.get("x-correlation-id")
            or get_request_id()
            or str(uuid.uuid4())
        )
        logger.info(
            "Queueing orchestrated evidence capture",
            extra={
                "request_id": get_request_id(),
                "correlation_id": request_correlation_id,
            },
        )
        IncidentEvidenceOrchestrator(db).begin_capture(
            org_id=org_id,
            incident_id=incident_id,
            actor_type="user",
            actor_id=str(current_user.id),
            window_start=window_start,
            window_end=window_end,
            correlation_id=request_correlation_id,
        )

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
    snapshot = build_case_snapshot(
        incident=incident,
        artifacts=artifacts,
        events=events,
        exports=exports,
    )

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
                unavailable_message=(
                    dashcam_reason_message(a.unavailable_reason_code)
                    if (a.artifact_type or "").startswith("dash_cam_video")
                    else a.unavailable_reason_detail
                ),
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
                expires_at_utc=e.expires_at_utc.isoformat()
                if e.expires_at_utc
                else None,
                created_at_utc=e.created_at_utc.isoformat()
                if e.created_at_utc
                else None,
                updated_at_utc=e.updated_at_utc.isoformat()
                if e.updated_at_utc
                else None,
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
        messaging_reliability=get_messaging_reliability_summary(
            db, org_id=incident.org_id, incident_id=incident.incident_id
        )
        if incident.org_id
        else {},
        completeness_percent=snapshot.completeness.percent,
        completeness_status=snapshot.completeness.status,
        readiness_state=snapshot.readiness.state,
        completeness_missing_items=snapshot.completeness.missing_items,
        blockers=[
            {
                "code": blocker.code,
                "message": blocker.message,
                "severity": blocker.severity,
                "category": blocker.missing_item.category,
                "resolvableBy": blocker.missing_item.resolvableBy,
                "actionHint": blocker.missing_item.actionHint,
                "blocksReadiness": blocker.blocks_readiness,
            }
            for blocker in snapshot.blockers.items
        ],
    )


@router.patch("/{incident_id}/status", response_model=IncidentStatusPatchResponse)
def patch_incident_status(
    incident_id: uuid.UUID,
    body: IncidentStatusPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    incident = get_incident(db, incident_id, org_ids=org_ids)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_modify_incident(context, incident))

    transition_capability = _required_transition_capability(
        str(incident.case_status), body.case_status
    )
    if transition_capability is not None and not has_capability(
        current_user.role, transition_capability
    ):
        raise HTTPException(
            status_code=403,
            detail=f"Transition requires capability '{transition_capability.value}'.",
        )

    transition_validation = validate_case_status_transition(
        from_status=str(incident.case_status),
        to_status=body.case_status,
        allow_privileged=transition_capability is not None,
    )
    if not transition_validation.allowed:
        raise HTTPException(
            status_code=409,
            detail=transition_validation.reason or "Invalid case status transition",
        )

    from_case_status = str(incident.case_status)
    incident.case_status = body.case_status
    transition_payload = {
        "from_case_status": from_case_status,
        "to_case_status": body.case_status,
        "transition_reason": body.reason,
        "privileged_transition": transition_capability is not None,
    }
    detailed_payload = _event_context_payload(
        actor_id=current_user.id,
        incident_id=incident_id,
        org_id=incident.org_id,
        reason=body.reason,
        previous={"case_status": from_case_status},
        new={"case_status": body.case_status},
    )
    db.flush()
    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.INCIDENT_UPDATED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=transition_payload,
    )
    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.INCIDENT_STATUS_CHANGED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=detailed_payload,
    )
    if body.case_status == "escalated":
        create_event(
            db,
            incident_id=incident_id,
            event_type=SystemEventType.INCIDENT_STATUS_ESCALATED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload=detailed_payload,
        )
    if body.case_status == "closed":
        create_event(
            db,
            incident_id=incident_id,
            event_type=SystemEventType.INCIDENT_STATUS_CLOSED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload=detailed_payload,
        )
    if from_case_status == "closed" and body.case_status != "closed":
        create_event(
            db,
            incident_id=incident_id,
            event_type=SystemEventType.INCIDENT_STATUS_REOPENED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload=detailed_payload,
        )
    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="incident.case_status.patch",
        event_type="incident_case_status_updated",
        outcome="success",
        incident_id=incident.incident_id,
        metadata=transition_payload,
    )
    db.commit()

    return IncidentStatusPatchResponse(
        incident_id=incident.incident_id,
        case_status=incident.case_status,
        transition_reason=body.reason,
    )


@router.patch("/{incident_id}/owner", response_model=IncidentOwnerPatchResponse)
def patch_incident_owner_endpoint(
    incident_id: uuid.UUID,
    body: IncidentOwnerPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    incident = get_incident(db, incident_id, org_ids=org_ids)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_modify_incident(context, incident))

    previous_owner_user_id = incident.owner_user_id
    incident = patch_incident_owner(
        db=db,
        incident=incident,
        org_ids=org_ids,
        actor_user_id=current_user.id,
        operation=body.operation,
        owner_user_id=body.owner_user_id,
    )
    event_payload = _event_context_payload(
        actor_id=current_user.id,
        incident_id=incident.incident_id,
        org_id=incident.org_id,
        reason=body.operation,
        previous={
            "owner_user_id": (
                str(previous_owner_user_id) if previous_owner_user_id else None
            )
        },
        new={"owner_user_id": str(incident.owner_user_id) if incident.owner_user_id else None},
    )
    if body.operation == "assign":
        event_type = SystemEventType.INCIDENT_OWNER_ASSIGNED
        audit_event_type = "incident_owner_assigned"
    elif body.operation == "reassign":
        event_type = SystemEventType.INCIDENT_OWNER_REASSIGNED
        audit_event_type = "incident_owner_reassigned"
    else:
        event_type = SystemEventType.INCIDENT_OWNER_CLEARED
        audit_event_type = "incident_owner_cleared"
    create_event(
        db,
        incident_id=incident.incident_id,
        event_type=event_type,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=event_payload,
    )
    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action=f"incident.owner.{body.operation}",
        event_type=audit_event_type,
        outcome="success",
        incident_id=incident.incident_id,
        metadata=event_payload,
    )
    db.commit()

    return IncidentOwnerPatchResponse(
        incident_id=incident.incident_id,
        owner_user_id=incident.owner_user_id,
        assigned_at=incident.owner_assigned_at_utc,
        assigned_by=incident.owner_assigned_by_user_id,
        team_queue=incident.team_queue,
        last_activity_at_utc=incident.last_activity_at_utc,
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

    return CreateExportResponse(
        export_id=export.export_id,
        status=export.status,
        progress_stage=export.progress_stage,
    )
