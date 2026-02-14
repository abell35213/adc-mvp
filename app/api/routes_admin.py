"""Admin API routes — vehicle and driver protocol management.

This module exposes administrative endpoints for configuring driver protocol
instructions, notification settings, and managing vehicles. The original
implementation used a static list of vehicles. This version introduces CRUD
operations backed by a persistent ``Vehicle`` model, enabling admins to
create, update and delete vehicles dynamically.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.schemas import (
    AdminVehicleSummary,
    DriverInstructionSetRequest,
    DriverInstructionSetResponse,
    DriverInstructionStep,
    DriverProtocolSettingsRequest,
    DriverProtocolSettingsResponse,
    QrPayloadResponse,
    RotateQrResponse,
)
from app.core.config import settings
from app.core.deps import get_current_user, require_roles
from app.db.models import (
    DriverInstructionSet,
    DriverInstructionStep as DriverInstructionStepModel,
    Event,
    Org,
    User,
    Vehicle,
    VehicleQrToken,
)
from app.db.session import get_db
from app.db.repo.users import get_user_org_ids
from app.db.repo.vehicles import (
    list_vehicles,
    get_vehicle,
    get_vehicle_by_adc_id,
    create_vehicle,
    update_vehicle,
    delete_vehicle,
)
from app.domain.system_event_types import SystemEventType

logger = logging.getLogger(__name__)

router = APIRouter()

# Instruction scopes allowed. See DriverInstructionSet.scope enum for valid values.
INSTRUCTION_SCOPES = {"default", "company", "insurer"}

# Default driver protocol steps used when seeding a new instruction set.
DEFAULT_DRIVER_PROTOCOL_STEPS: List[dict] = [
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


# Dependency alias for admin role checks. We use require_roles to enforce that
# the current user has the "admin" role. If the user lacks this role a 403
# error is raised automatically.
_require_admin = require_roles(["admin"])  # type: ignore


def _get_admin_org(db: Session, admin: User) -> Org:
    org_ids = get_user_org_ids(db, admin.id)
    org_id = org_ids[0] if org_ids else None
    org = db.query(Org).filter(Org.id == org_id).first() if org_id else None
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
    steps: list[DriverInstructionStepModel] = []
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
    admin: User = Depends(_require_admin),
):
    org = _get_admin_org(db, admin)
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
    admin: User = Depends(_require_admin),
):
    org = _get_admin_org(db, admin)
    org.instruction_source = _normalize_instruction_scope(body.instruction_source)
    org.require_driver_ack = body.require_ack
    org.sms_enabled = body.sms_enabled
    org.voice_enabled = body.voice_enabled
    org.safety_manager_phone = body.safety_manager_phone
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
    admin: User = Depends(_require_admin),
):
    org = _get_admin_org(db, admin)
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
    admin: User = Depends(_require_admin),
):
    org = _get_admin_org(db, admin)
    resolved_scope = _normalize_instruction_scope(body.scope)
    instruction_set = _get_or_create_instruction_set(db, org.id, resolved_scope)
    db.query(DriverInstructionStepModel).filter(
        DriverInstructionStepModel.instruction_set_id
        == instruction_set.instruction_set_id
    ).delete(synchronize_session=False)
    new_steps: list[DriverInstructionStepModel] = []
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
    admin: User = Depends(_require_admin),
):
    org = _get_admin_org(db, admin)
    resolved_scope = _normalize_instruction_scope(scope or org.instruction_source)
    instruction_set = _get_or_create_instruction_set(db, org.id, resolved_scope)
    db.query(DriverInstructionStepModel).filter(
        DriverInstructionStepModel.instruction_set_id
        == instruction_set.instruction_set_id
    ).delete(synchronize_session=False)
    steps = _seed_instruction_steps(db, instruction_set)
    db.commit()
    return DriverInstructionSetResponse(
        instruction_set_id=instruction_set.instruction_set_id,
        scope=resolved_scope,
        steps=_serialize_instruction_steps(steps),
    )


# ── Vehicle management endpoints ─────────────────────────────────────────

class VehicleCreateBody(BaseModel):
    adc_vehicle_id: str = Field(..., description="Unique vehicle identifier used in QR codes.")
    display_label: str | None = Field(None, description="Human‑friendly label shown in UIs.")
    make: str | None = None
    model: str | None = None
    year: int | None = None
    vin: str | None = Field(None, description="VIN number for the vehicle.")


class VehicleUpdateBody(BaseModel):
    display_label: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    vin: str | None = None
    is_active: bool | None = None


@router.get(
    "/vehicles",
    response_model=list[AdminVehicleSummary],
)
def list_admin_vehicles(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
):
    """Return all vehicles belonging to the admin's organization(s)."""
    org_ids = get_user_org_ids(db, admin.id)
    vehicles = list_vehicles(db, org_ids=org_ids)
    return [
        AdminVehicleSummary(
            adc_vehicle_id=v.adc_vehicle_id,
            display_label=v.display_name or v.adc_vehicle_id,
        )
        for v in vehicles
    ]


@router.post(
    "/vehicles",
    response_model=AdminVehicleSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_vehicle(
    body: VehicleCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
):
    """Create a new vehicle within the admin's active organization."""
    org_ids = get_user_org_ids(db, admin.id)
    org_id = org_ids[0] if org_ids else None
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active organization")

    # Check uniqueness of adc_vehicle_id within org
    existing = get_vehicle_by_adc_id(db, body.adc_vehicle_id, org_ids=[org_id])
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vehicle ID already exists")

    vehicle = create_vehicle(
        db,
        org_id=org_id,
        adc_vehicle_id=body.adc_vehicle_id,
        make=body.make,
        model=body.model,
        year=body.year,
        vin=body.vin,
        display_name=body.display_label or body.adc_vehicle_id,
    )
    return AdminVehicleSummary(
        adc_vehicle_id=vehicle.adc_vehicle_id,
        display_label=vehicle.display_name or vehicle.adc_vehicle_id,
    )


@router.put(
    "/vehicles/{vehicle_id}",
    response_model=AdminVehicleSummary,
)
def update_admin_vehicle(
    vehicle_id: uuid.UUID,
    body: VehicleUpdateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
):
    """Update an existing vehicle owned by the admin's organization(s)."""
    org_ids = get_user_org_ids(db, admin.id)
    vehicle = get_vehicle(db, vehicle_id, org_ids=org_ids)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    updated = update_vehicle(
        db,
        vehicle_id=vehicle_id,
        adc_vehicle_id=None,
        make=body.make,
        model=body.model,
        year=body.year,
        vin=body.vin,
        display_name=body.display_label,
        is_active=body.is_active,
    )
    return AdminVehicleSummary(
        adc_vehicle_id=updated.adc_vehicle_id,
        display_label=updated.display_name or updated.adc_vehicle_id,
    )


@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_admin_vehicle(
    vehicle_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
):
    """Delete a vehicle entirely.

    In most cases, deactivation (via update) is preferred over deletion.
    """
    org_ids = get_user_org_ids(db, admin.id)
    vehicle = get_vehicle(db, vehicle_id, org_ids=org_ids)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    delete_vehicle(db, vehicle_id)
    return None


# ── QR token management endpoints (unchanged) ─────────────────────────

@router.post(
    "/vehicles/{vehicle_id}/qr/rotate",
    response_model=RotateQrResponse,
    status_code=status.HTTP_201_CREATED,
)
def rotate_qr(
    vehicle_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_admin),
):
    """Revoke the current active QR token for a vehicle and issue a new one."""
    # Revoke existing active token(s)
    active_tokens = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.adc_vehicle_id == vehicle_id,
            VehicleQrToken.status == "active",
        )
        .all()
    )
    for tok in active_tokens:
        tok.status = "rotated"

    # Generate a new 32‑byte base64url token
    new_token = secrets.token_urlsafe(32)

    # Determine org_id from the admin's org membership
    org_ids = get_user_org_ids(db, admin.id)
    org_id = org_ids[0] if org_ids else None

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
    db.commit()
    logger.info(
        "VEHICLE_QR_ROTATED vehicle=%s admin=%s",
        vehicle_id,
        admin.id,
    )
    return RotateQrResponse(qr_token=new_token)


@router.get(
    "/vehicles/{vehicle_id}/qr",
    response_model=QrPayloadResponse,
)
def get_qr_payload(
    vehicle_id: str,
    admin: User = Depends(_require_admin),
):
    """Return the deep link string for QR code generation."""
    scheme = settings.DRIVER_APP_DEEPLINK_SCHEME
    deep_link = f"{scheme}://vehicle/{vehicle_id}"
    return QrPayloadResponse(deep_link=deep_link)
