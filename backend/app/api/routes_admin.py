"""Admin API routes — vehicle QR token management."""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.schemas import (
    AuditSearchResponseItem,
    AdminVehicleSummary,
    DriverInstructionSetRequest,
    DriverInstructionSetResponse,
    DriverInstructionStep,
    DriverProtocolSettingsRequest,
    DriverProtocolSettingsResponse,
    IntegrationHealthItem,
    JobExecutionMetaItem,
    JobExecutionMetaSummary,
    MessagingReliabilityResponse,
    OpsAnomalyItem,
    OpsDashboardResponse,
    OpsFailedExportItem,
    OpsFailedNotificationItem,
    OpsIncidentItem,
    QrPayloadResponse,
    RotateQrResponse,
)
from app.audit.emitter import emit_audit_event
from app.core.config import settings
from app.core.deps import get_current_user
from app.case_ops.service import build_dashboard_snapshot
from app.security.permissions import Capability
from app.security.authn import build_user_auth_context
from app.security.authz import can_access_admin_org, require_policy
from app.db.models import (
    Artifact,
    AuditEvent,
    DriverInstructionSet,
    DriverInstructionStep as DriverInstructionStepModel,
    Event,
    Export,
    Incident,
    JobExecutionMeta,
    Org,
    User,
    VehicleQrToken,
)
from app.db.session import get_db
from app.db.repo.message_operations import get_messaging_reliability_summary
from app.domain.system_event_types import SystemEventType
from app.db.repo.job_execution_meta import (
    list_ops_jobs_with_db,
    summarize_ops_jobs_with_db,
)

logger = logging.getLogger(__name__)

router = APIRouter()

INSTRUCTION_SCOPES = {"default", "company", "insurer"}
OPS_ALLOWED_ROLES = {"system_admin", "org_admin", "admin"}

DEFAULT_DRIVER_PROTOCOL_STEPS = [
    {
        "title": "Get to safety",
        "body": "Move to a safe location and turn on hazard lights if possible.",
        "enabled": True,
    },
    {
        "title": "Call your safety manager",
        "body": "Contact your safety manager to report the incident and await next steps.",
        "enabled": True,
    },
    {
        "title": "Document the scene",
        "body": "Take photos of vehicles, damage, and the surrounding area.",
        "enabled": True,
    },
]

ADMIN_VEHICLES = [
    {"adc_vehicle_id": "veh-101", "display_label": "Truck 101"},
    {"adc_vehicle_id": "veh-204", "display_label": "Van 204"},
    {"adc_vehicle_id": "veh-305", "display_label": "Trailer 305"},
]


def _get_admin_org(db: Session, admin_org_id: uuid.UUID) -> Org:
    org = db.query(Org).filter(Org.id == admin_org_id).first()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org


def _normalize_instruction_scope(scope: str) -> str:
    if scope not in INSTRUCTION_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid instruction scope",
        )
    return scope


def _require_admin_policy(
    db: Session,
    *,
    allowed: bool,
    actor_id: uuid.UUID,
    org_id: uuid.UUID | None,
    action: str,
    metadata: dict | None = None,
) -> None:
    if allowed:
        return
    emit_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(actor_id),
        action=action,
        event_type="authorization_failed",
        outcome="failure",
        metadata={"should_log": True, **(metadata or {})},
    )
    require_policy(False)


def _can_access_ops_views(context) -> bool:
    return context.user.role in OPS_ALLOWED_ROLES and bool(context.org_ids)


def _get_or_create_instruction_set(
    db: Session, org_id: uuid.UUID, scope: str
) -> DriverInstructionSet:
    instruction_set = (
        db.query(DriverInstructionSet)
        .filter(
            DriverInstructionSet.org_id == org_id,
            DriverInstructionSet.scope == scope,
        )
        .first()
    )
    if instruction_set is None:
        instruction_set = DriverInstructionSet(org_id=org_id, scope=scope)
        db.add(instruction_set)
        db.flush()
    return instruction_set


def _seed_instruction_steps(
    db: Session, instruction_set: DriverInstructionSet
) -> list[DriverInstructionStepModel]:
    steps = []
    for index, step in enumerate(DEFAULT_DRIVER_PROTOCOL_STEPS, start=1):
        step_row = DriverInstructionStepModel(
            instruction_set_id=instruction_set.instruction_set_id,
            step_order=index,
            title=step["title"],
            body=step["body"],
            enabled=step["enabled"],
        )
        steps.append(step_row)
        db.add(step_row)
    db.flush()
    return steps


def _serialize_instruction_steps(
    steps: list[DriverInstructionStepModel],
) -> list[DriverInstructionStep]:
    return [
        DriverInstructionStep(
            step_id=step.step_id,
            order=step.step_order,
            title=step.title,
            body=step.body,
            enabled=step.enabled,
        )
        for step in steps
    ]


@router.get(
    "/driver-protocol/settings",
    response_model=DriverProtocolSettingsResponse,
)
def get_driver_protocol_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.DRIVER_PROTOCOL_WRITE
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="driver_protocol.settings.read",
    )
    org = _get_admin_org(db, context.org_ids[0])
    return DriverProtocolSettingsResponse(
        instruction_source=org.instruction_source,
        require_ack=org.require_driver_ack,
        sms_enabled=org.sms_enabled,
        voice_enabled=org.voice_enabled,
        safety_manager_phone=org.safety_manager_phone,
    )


@router.put(
    "/driver-protocol/settings",
    response_model=DriverProtocolSettingsResponse,
)
def update_driver_protocol_settings(
    body: DriverProtocolSettingsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.DRIVER_PROTOCOL_WRITE
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="driver_protocol.settings.update",
    )
    org = _get_admin_org(db, context.org_ids[0])
    org.instruction_source = _normalize_instruction_scope(body.instruction_source)
    org.require_driver_ack = body.require_ack
    org.sms_enabled = body.sms_enabled
    org.voice_enabled = body.voice_enabled
    org.safety_manager_phone = body.safety_manager_phone
    emit_audit_event(
        db,
        org_id=org.id,
        actor_type="user",
        actor_id=str(admin.id),
        action="driver_protocol.settings.update",
        event_type="config_updated",
        outcome="success",
        metadata={
            "instruction_source": org.instruction_source,
            "require_ack": org.require_driver_ack,
            "sms_enabled": org.sms_enabled,
            "voice_enabled": org.voice_enabled,
            "support_access_escalation": bool(org.sms_enabled or org.voice_enabled),
        },
    )
    db.commit()
    return DriverProtocolSettingsResponse(
        instruction_source=org.instruction_source,
        require_ack=org.require_driver_ack,
        sms_enabled=org.sms_enabled,
        voice_enabled=org.voice_enabled,
        safety_manager_phone=org.safety_manager_phone,
    )


@router.get(
    "/driver-protocol/instructions",
    response_model=DriverInstructionSetResponse,
)
def get_driver_protocol_instructions(
    scope: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.DRIVER_PROTOCOL_READ
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="driver_protocol.instructions.read",
    )
    org = _get_admin_org(db, context.org_ids[0])
    resolved_scope = _normalize_instruction_scope(scope or org.instruction_source)
    instruction_set = _get_or_create_instruction_set(db, org.id, resolved_scope)
    steps = (
        db.query(DriverInstructionStepModel)
        .filter(
            DriverInstructionStepModel.instruction_set_id
            == instruction_set.instruction_set_id
        )
        .order_by(DriverInstructionStepModel.step_order)
        .all()
    )
    if not steps:
        steps = _seed_instruction_steps(db, instruction_set)
        db.commit()
    return DriverInstructionSetResponse(
        instruction_set_id=instruction_set.instruction_set_id,
        scope=resolved_scope,
        steps=_serialize_instruction_steps(steps),
    )


@router.put(
    "/driver-protocol/instructions",
    response_model=DriverInstructionSetResponse,
)
def update_driver_protocol_instructions(
    body: DriverInstructionSetRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.DRIVER_PROTOCOL_WRITE
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="driver_protocol.instructions.update",
    )
    org = _get_admin_org(db, context.org_ids[0])
    resolved_scope = _normalize_instruction_scope(body.scope)
    instruction_set = _get_or_create_instruction_set(db, org.id, resolved_scope)
    db.query(DriverInstructionStepModel).filter(
        DriverInstructionStepModel.instruction_set_id
        == instruction_set.instruction_set_id
    ).delete(synchronize_session=False)
    new_steps = []
    for step in body.steps:
        step_row = DriverInstructionStepModel(
            instruction_set_id=instruction_set.instruction_set_id,
            step_order=step.order,
            title=step.title,
            body=step.body,
            enabled=step.enabled,
        )
        db.add(step_row)
        new_steps.append(step_row)
    emit_audit_event(
        db,
        org_id=org.id,
        actor_type="user",
        actor_id=str(admin.id),
        action="driver_protocol.instructions.update",
        event_type="instruction_set_updated",
        outcome="success",
        metadata={"scope": resolved_scope, "step_count": len(new_steps)},
    )
    db.commit()
    return DriverInstructionSetResponse(
        instruction_set_id=instruction_set.instruction_set_id,
        scope=resolved_scope,
        steps=_serialize_instruction_steps(new_steps),
    )


@router.post(
    "/driver-protocol/instructions/reset",
    response_model=DriverInstructionSetResponse,
)
def reset_driver_protocol_instructions(
    scope: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.DRIVER_PROTOCOL_WRITE
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="driver_protocol.instructions.reset",
    )
    org = _get_admin_org(db, context.org_ids[0])
    resolved_scope = _normalize_instruction_scope(scope or org.instruction_source)
    instruction_set = _get_or_create_instruction_set(db, org.id, resolved_scope)
    db.query(DriverInstructionStepModel).filter(
        DriverInstructionStepModel.instruction_set_id
        == instruction_set.instruction_set_id
    ).delete(synchronize_session=False)
    steps = _seed_instruction_steps(db, instruction_set)
    emit_audit_event(
        db,
        org_id=org.id,
        actor_type="user",
        actor_id=str(admin.id),
        action="driver_protocol.instructions.reset",
        event_type="instruction_set_updated",
        outcome="success",
        metadata={"scope": resolved_scope, "reset": True, "step_count": len(steps)},
    )
    db.commit()
    return DriverInstructionSetResponse(
        instruction_set_id=instruction_set.instruction_set_id,
        scope=resolved_scope,
        steps=_serialize_instruction_steps(steps),
    )


@router.get("/vehicles", response_model=list[AdminVehicleSummary])
def list_admin_vehicles(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.VEHICLE_QR_READ
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="admin.vehicles.list",
    )
    return [AdminVehicleSummary(**vehicle) for vehicle in ADMIN_VEHICLES]


@router.post(
    "/vehicles/{vehicle_id}/qr/rotate",
    response_model=RotateQrResponse,
    status_code=201,
)
def rotate_qr(
    vehicle_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    """Revoke the current active QR token for a vehicle and issue a new one."""
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.VEHICLE_QR_WRITE
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="admin.vehicle_qr.rotate",
    )

    # Revoke existing active token(s)
    active_tokens = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.adc_vehicle_id == vehicle_id,
            VehicleQrToken.status == "active",
            VehicleQrToken.org_id.in_(context.org_ids),
        )
        .all()
    )
    for tok in active_tokens:
        tok.status = "rotated"

    # Generate a new 32-byte base64url token
    new_token = secrets.token_urlsafe(32)

    # Determine org_id from the admin's org membership
    org_id = context.org_ids[0]

    qr = VehicleQrToken(
        qr_token=new_token,
        org_id=org_id,
        adc_vehicle_id=vehicle_id,
        status="active",
        rotated_from_token=active_tokens[0].qr_token if active_tokens else None,
    )
    db.add(qr)

    # Emit VEHICLE_QR_ROTATED event
    token_hash = hashlib.sha256(new_token.encode()).hexdigest()
    event = Event(
        org_id=org_id,
        incident_id=None,
        event_type=SystemEventType.VEHICLE_QR_ROTATED.value,
        actor_type="admin",
        actor_id=str(admin.id),
        payload={
            "adc_vehicle_id": vehicle_id,
            "new_token_sha256": token_hash,
        },
    )
    db.add(event)
    emit_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(admin.id),
        action="admin.vehicle_qr.rotate",
        event_type="credential_updated",
        outcome="success",
        metadata={"adc_vehicle_id": vehicle_id, "token_sha256": token_hash},
    )
    db.commit()

    logger.info(
        "VEHICLE_QR_ROTATED vehicle=%s admin=%s",
        vehicle_id,
        admin.id,
    )

    return RotateQrResponse(qr_token=new_token)


@router.get("/vehicles/{vehicle_id}/qr", response_model=QrPayloadResponse)
def get_qr_payload(
    vehicle_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    """Return the deep link string for QR code generation."""
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.VEHICLE_QR_READ
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="admin.vehicle_qr.read",
    )
    scheme = settings.DRIVER_APP_DEEPLINK_SCHEME
    deep_link = f"{scheme}://vehicle/{vehicle_id}"
    return QrPayloadResponse(deep_link=deep_link)


@router.get("/ops/jobs/summary", response_model=JobExecutionMetaSummary)
def get_ops_jobs_summary(
    stale_after_minutes: int = 15,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.EXPORT_READ
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="admin.ops.jobs.summary",
    )
    return JobExecutionMetaSummary(
        **summarize_ops_jobs_with_db(db=db, stale_after_minutes=stale_after_minutes)
    )


@router.get("/ops/jobs", response_model=list[JobExecutionMetaItem])
def list_ops_job_failures(
    stale_after_minutes: int = 15,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=can_access_admin_org(
            context, context.org_ids[0], Capability.EXPORT_READ
        ),
        actor_id=admin.id,
        org_id=context.org_ids[0],
        action="admin.ops.jobs.list",
    )
    rows = list_ops_jobs_with_db(
        db=db,
        statuses={"failed", "retrying", "running", "queued"},
        stale_after_minutes=stale_after_minutes,
    )
    return [
        JobExecutionMetaItem(
            celery_task_id=row.celery_task_id,
            task_name=row.task_name,
            task_type=row.task_type,
            status=row.status,
            retry_count=row.retry_count,
            max_retries=row.max_retries,
            retry_category=row.retry_category,
            should_retry=row.should_retry,
            next_retry_at_utc=row.next_retry_at_utc,
            started_at_utc=row.started_at_utc,
            finished_at_utc=row.finished_at_utc,
            last_heartbeat_at_utc=row.last_heartbeat_at_utc,
            last_error=row.last_error,
            created_at_utc=row.created_at_utc,
            updated_at_utc=row.updated_at_utc,
        )
        for row in rows
    ]


@router.get("/ops/dashboard", response_model=OpsDashboardResponse)
def get_ops_dashboard(
    stale_after_minutes: int = 15,
    lookback_hours: int = 24,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=_can_access_ops_views(context),
        actor_id=admin.id,
        org_id=context.org_ids[0] if context.org_ids else None,
        action="admin.ops.dashboard.read",
        metadata={"required_roles": sorted(OPS_ALLOWED_ROLES)},
    )
    org_id = context.org_ids[0]
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(minutes=max(1, stale_after_minutes))
    lookback_cutoff = now - timedelta(hours=max(1, lookback_hours))

    stuck_incidents = (
        db.query(Incident)
        .filter(
            Incident.org_id == org_id,
            Incident.status == "evidence_capturing",
            Incident.created_at_utc <= stale_cutoff,
        )
        .order_by(Incident.created_at_utc.asc())
        .limit(50)
        .all()
    )

    missing_evidence_rows = (
        db.query(Incident, func.count(Artifact.artifact_id).label("missing_count"))
        .outerjoin(
            Artifact,
            Artifact.incident_id == Incident.incident_id,
        )
        .filter(
            Incident.org_id == org_id,
            Incident.status != "closed",
            or_(Artifact.artifact_id.is_(None), Artifact.status != "captured"),
        )
        .group_by(Incident.incident_id)
        .order_by(Incident.created_at_utc.asc())
        .limit(50)
        .all()
    )

    failed_notifications = (
        db.query(JobExecutionMeta)
        .filter(
            JobExecutionMeta.task_type == "notification_tasks",
            JobExecutionMeta.status.in_(("failed", "retrying")),
        )
        .order_by(JobExecutionMeta.updated_at_utc.desc())
        .limit(50)
        .all()
    )

    failed_exports = (
        db.query(Export)
        .filter(Export.org_id == org_id, Export.status == "failed")
        .order_by(Export.updated_at_utc.desc())
        .limit(50)
        .all()
    )

    integration_rows = (
        db.query(
            JobExecutionMeta.task_type,
            func.count(JobExecutionMeta.id).label("failure_count"),
            func.max(JobExecutionMeta.updated_at_utc).label("last_failure_at_utc"),
        )
        .filter(JobExecutionMeta.status.in_(("failed", "retrying")))
        .group_by(JobExecutionMeta.task_type)
        .all()
    )
    known_integration_keys = {"evidence_tasks", "notification_tasks", "export_tasks"}
    integration_health: list[IntegrationHealthItem] = []
    for key in ("evidence_tasks", "notification_tasks", "export_tasks"):
        row = next((item for item in integration_rows if item.task_type == key), None)
        if row is None:
            integration_health.append(
                IntegrationHealthItem(
                    integration_key=key,
                    status="healthy",
                    failure_count=0,
                )
            )
            continue
        integration_health.append(
            IntegrationHealthItem(
                integration_key=key,
                status="degraded",
                failure_count=int(row.failure_count or 0),
                last_failure_at_utc=row.last_failure_at_utc,
                details="Recent failed or retrying job executions detected.",
            )
        )
    for row in integration_rows:
        if row.task_type in known_integration_keys:
            continue
        integration_health.append(
            IntegrationHealthItem(
                integration_key=row.task_type,
                status="degraded",
                failure_count=int(row.failure_count or 0),
                last_failure_at_utc=row.last_failure_at_utc,
                details="Recent failed or retrying job executions detected.",
            )
        )

    anomaly_events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.org_id == org_id,
            AuditEvent.occurred_at_utc >= lookback_cutoff,
            or_(
                AuditEvent.event_type == "authorization_failed",
                AuditEvent.outcome == "failure",
                AuditEvent.action.ilike("%security%"),
            ),
        )
        .order_by(AuditEvent.occurred_at_utc.desc())
        .limit(100)
        .all()
    )
    case_metric_incidents = (
        db.query(Incident)
        .filter(Incident.org_id == org_id)
        .all()
    )
    incident_ids = [row.incident_id for row in case_metric_incidents]
    artifacts_by_incident: dict[uuid.UUID, list[Artifact]] = {}
    events_by_incident: dict[uuid.UUID, list[Event]] = {}
    exports_by_incident: dict[uuid.UUID, list[Export]] = {}
    if incident_ids:
        for artifact in db.query(Artifact).filter(Artifact.incident_id.in_(incident_ids)).all():
            artifacts_by_incident.setdefault(artifact.incident_id, []).append(artifact)
        for event in db.query(Event).filter(Event.incident_id.in_(incident_ids)).all():
            events_by_incident.setdefault(event.incident_id, []).append(event)
        for export in db.query(Export).filter(Export.incident_id.in_(incident_ids)).all():
            exports_by_incident.setdefault(export.incident_id, []).append(export)
    case_metrics = build_dashboard_snapshot(
        incidents=case_metric_incidents,
        artifacts_by_incident=artifacts_by_incident,
        events_by_incident=events_by_incident,
        exports_by_incident=exports_by_incident,
    )
    emit_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(admin.id),
        action="admin.ops.dashboard.read",
        event_type="ops_dashboard_viewed",
        outcome="success",
        metadata={
            "stuck_incident_count": len(stuck_incidents),
            "missing_evidence_count": len(missing_evidence_rows),
            "failed_notification_count": len(failed_notifications),
            "failed_export_count": len(failed_exports),
            "anomaly_count": len(anomaly_events),
        },
    )
    return OpsDashboardResponse(
        stuck_incidents=[
            OpsIncidentItem(
                incident_id=row.incident_id,
                status=row.status,
                created_at_utc=row.created_at_utc,
                adc_vehicle_id=row.adc_vehicle_id,
                adc_driver_id=row.adc_driver_id,
                reason="Evidence capture has exceeded stale threshold.",
            )
            for row in stuck_incidents
        ],
        missing_evidence_incidents=[
            OpsIncidentItem(
                incident_id=incident.incident_id,
                status=incident.status,
                created_at_utc=incident.created_at_utc,
                adc_vehicle_id=incident.adc_vehicle_id,
                adc_driver_id=incident.adc_driver_id,
                reason=f"{missing_count} evidence artifacts not captured.",
            )
            for incident, missing_count in missing_evidence_rows
        ],
        failed_notifications=[
            OpsFailedNotificationItem(
                celery_task_id=row.celery_task_id,
                status=row.status,
                retry_count=row.retry_count,
                max_retries=row.max_retries,
                last_error=row.last_error,
                updated_at_utc=row.updated_at_utc,
            )
            for row in failed_notifications
        ],
        failed_exports=[
            OpsFailedExportItem(
                export_id=row.export_id,
                incident_id=row.incident_id,
                export_type=row.export_type,
                status=row.status,
                error_message=row.error_message,
                updated_at_utc=row.updated_at_utc,
            )
            for row in failed_exports
        ],
        integration_health=integration_health,
        recent_anomalies=[
            OpsAnomalyItem(
                audit_event_id=row.id,
                occurred_at_utc=row.occurred_at_utc,
                action=row.action,
                event_type=row.event_type,
                outcome=row.outcome,
                actor_id=row.actor_id,
                metadata=row.metadata_json or {},
            )
            for row in anomaly_events
        ],
        org_messaging_reliability=MessagingReliabilityResponse(
            **get_messaging_reliability_summary(db, org_id=org_id)
        ),
        case_metrics={
            "total_open_cases": case_metrics.total_open_cases,
            "not_ready_cases": case_metrics.not_ready_cases,
            "conditionally_ready_cases": case_metrics.conditionally_ready_cases,
            "ready_for_export_cases": case_metrics.ready_for_export_cases,
            "exported_cases": case_metrics.exported_cases,
            "closed_cases": case_metrics.closed_cases,
            "cases_with_critical_blockers": case_metrics.cases_with_critical_blockers,
            "cases_with_important_blockers": case_metrics.cases_with_important_blockers,
            "aging": {
                "average_age_days": case_metrics.aging.average_age_days,
                "p95_age_days": case_metrics.aging.p95_age_days,
                "over_24h": case_metrics.aging.over_24h,
                "over_72h": case_metrics.aging.over_72h,
                "over_7d": case_metrics.aging.over_7d,
            },
        },
    )


@router.get(
    "/ops/messaging-reliability",
    response_model=MessagingReliabilityResponse,
)
def ops_messaging_reliability(
    incident_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=_can_access_ops_views(context),
        actor_id=admin.id,
        org_id=context.org_ids[0] if context.org_ids else None,
        action="admin.ops.messaging_reliability.read",
        metadata={"required_roles": sorted(OPS_ALLOWED_ROLES)},
    )
    org_id = context.org_ids[0]
    return MessagingReliabilityResponse(
        **get_messaging_reliability_summary(db, org_id=org_id, incident_id=incident_id)
    )


@router.get("/ops/audit-search", response_model=list[AuditSearchResponseItem])
def audit_search(
    q: str | None = None,
    action: str | None = None,
    event_type: str | None = None,
    outcome: str | None = None,
    actor_id: str | None = None,
    lookback_hours: int = 168,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, admin)
    _require_admin_policy(
        db,
        allowed=_can_access_ops_views(context),
        actor_id=admin.id,
        org_id=context.org_ids[0] if context.org_ids else None,
        action="admin.ops.audit.search",
        metadata={"required_roles": sorted(OPS_ALLOWED_ROLES)},
    )
    org_id = context.org_ids[0]
    lookback_cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, lookback_hours))
    query = db.query(AuditEvent).filter(
        AuditEvent.org_id == org_id,
        AuditEvent.occurred_at_utc >= lookback_cutoff,
    )
    if action:
        query = query.filter(AuditEvent.action.ilike(f"%{action}%"))
    if event_type:
        query = query.filter(AuditEvent.event_type.ilike(f"%{event_type}%"))
    if outcome:
        query = query.filter(AuditEvent.outcome == outcome)
    if actor_id:
        query = query.filter(AuditEvent.actor_id.ilike(f"%{actor_id}%"))
    if q:
        query = query.filter(
            or_(
                AuditEvent.action.ilike(f"%{q}%"),
                AuditEvent.event_type.ilike(f"%{q}%"),
                AuditEvent.actor_id.ilike(f"%{q}%"),
            )
        )
    rows = query.order_by(AuditEvent.occurred_at_utc.desc()).limit(max(1, min(limit, 250))).all()
    emit_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(admin.id),
        action="admin.ops.audit.search",
        event_type="ops_audit_search_performed",
        outcome="success",
        metadata={
            "query_text": q,
            "action_filter": action,
            "event_type_filter": event_type,
            "outcome_filter": outcome,
            "result_count": len(rows),
        },
    )
    return [
        AuditSearchResponseItem(
            audit_event_id=row.id,
            org_id=row.org_id,
            incident_id=row.incident_id,
            export_id=row.export_id,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            action=row.action,
            event_type=row.event_type,
            outcome=row.outcome,
            occurred_at_utc=row.occurred_at_utc,
            metadata=row.metadata_json or {},
        )
        for row in rows
    ]
