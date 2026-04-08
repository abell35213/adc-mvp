"""Admin API routes — vehicle QR token management."""

import hashlib
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    AdminVehicleSummary,
    DriverInstructionSetRequest,
    DriverInstructionSetResponse,
    DriverInstructionStep,
    DriverProtocolSettingsRequest,
    DriverProtocolSettingsResponse,
    JobExecutionMetaItem,
    JobExecutionMetaSummary,
    QrPayloadResponse,
    RotateQrResponse,
)
from app.audit.emitter import emit_audit_event
from app.core.config import settings
from app.core.deps import get_current_user
from app.security.permissions import Capability
from app.security.authn import build_user_auth_context
from app.security.authz import can_access_admin_org, require_policy
from app.db.models import (
    DriverInstructionSet,
    DriverInstructionStep as DriverInstructionStepModel,
    Event,
    Org,
    User,
    VehicleQrToken,
)
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.db.repo.job_execution_meta import (
    list_ops_jobs_with_db,
    summarize_ops_jobs_with_db,
)

logger = logging.getLogger(__name__)

router = APIRouter()

INSTRUCTION_SCOPES = {"default", "company", "insurer"}

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
