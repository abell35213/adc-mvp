"""Vehicle QR deployment routes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.error_responses import raise_api_error
from app.api.schemas import (
    ApiErrorResponse,
    VehicleQrBulkGenerateRequest,
    VehicleQrBulkGenerateResponse,
    VehicleQrGenerateResponse,
    VehicleQrStatsResponse,
)
from app.core.deps import get_current_user
from app.db.models import Event, OrgVehicleRegistry, User, VehicleQrToken
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability
from app.services.pdf_render import render_pdf
from app.services.qr_image import qr_png_data_uri

router = APIRouter(prefix="/org", tags=["qr-deployment"])


def _first_org_id(user_context) -> uuid.UUID:
    return user_context.org_ids[0]


def _require_qr_access(user: User, *, write: bool = False) -> None:
    capability = Capability.VEHICLE_QR_WRITE if write else Capability.VEHICLE_QR_READ
    if not has_capability(cast(str | None, user.role), capability):
        raise_api_error(
            status_code=403,
            message="You do not have permission to manage vehicle QR deployment.",
            code="ACCESS_DENIED",
        )


def _get_required_vehicle(db: Session, *, org_id: uuid.UUID, vehicle_id: str) -> OrgVehicleRegistry:
    vehicle = (
        db.query(OrgVehicleRegistry)
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.unit_number == vehicle_id,
            OrgVehicleRegistry.is_active.is_(True),
        )
        .first()
    )
    if vehicle is None:
        raise_api_error(status_code=404, message="Vehicle not found.", code="RESOURCE_NOT_FOUND")
    return cast(OrgVehicleRegistry, vehicle)


def _emit_vehicle_qr_event(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    vehicle_id: str,
    payload: dict,
) -> None:
    db.add(
        Event(
            org_id=org_id,
            incident_id=None,
            event_type=action,
            actor_type="admin",
            actor_id=str(actor_id),
            payload={"adc_vehicle_id": vehicle_id, **payload},
        )
    )


def _vehicle_qr_stats(db: Session, *, org_id: uuid.UUID) -> VehicleQrStatsResponse:
    required_rows = (
        db.query(OrgVehicleRegistry)
        .filter(OrgVehicleRegistry.org_id == org_id, OrgVehicleRegistry.is_active.is_(True))
        .all()
    )
    required_ids = {row.unit_number for row in required_rows}
    generated_ids = {
        row.adc_vehicle_id
        for row in db.query(VehicleQrToken)
        .filter(VehicleQrToken.org_id == org_id, VehicleQrToken.status == "active")
        .all()
    }
    distributed_count = sum(1 for row in required_rows if row.qr_deployment_status in {"distributed", "confirmed"})
    confirmed_count = sum(1 for row in required_rows if row.qr_deployment_status == "confirmed")
    blockers: list[str] = []
    if len(required_ids - generated_ids) > 0:
        blockers.append("required_vehicles_not_generated")
    if distributed_count < len(required_rows):
        blockers.append("required_vehicles_not_distributed")
    return VehicleQrStatsResponse(
        required_vehicle_count=len(required_rows),
        generated_count=len(required_ids.intersection(generated_ids)),
        distributed_count=distributed_count,
        confirmed_count=confirmed_count,
        coverage_blockers=blockers,
    )


@router.post(
    "/vehicles/{vehicle_id}/generate-qr",
    response_model=VehicleQrGenerateResponse,
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Generate or return active vehicle QR token",
)
def generate_vehicle_qr(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_qr_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    vehicle = _get_required_vehicle(db, org_id=org_id, vehicle_id=vehicle_id)
    vehicle_row = cast(Any, vehicle)

    active_token = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.adc_vehicle_id == vehicle_row.unit_number,
            VehicleQrToken.status == "active",
        )
        .first()
    )
    if active_token is None:
        active_token = VehicleQrToken(
            qr_token=secrets.token_urlsafe(32),
            org_id=org_id,
            adc_vehicle_id=vehicle_row.unit_number,
            status="active",
        )
        db.add(active_token)

    vehicle_row.qr_deployment_status = "generated"
    vehicle_row.qr_generated_at_utc = datetime.now(timezone.utc)
    token_row = cast(Any, active_token)
    token_hash = hashlib.sha256(cast(str, token_row.qr_token).encode()).hexdigest()
    _emit_vehicle_qr_event(
        db,
        org_id=org_id,
        actor_id=cast(uuid.UUID, current_user.id),
        action="vehicle_qr_generated",
        vehicle_id=cast(str, vehicle_row.unit_number),
        payload={"token_sha256": token_hash},
    )
    db.commit()
    return VehicleQrGenerateResponse(
        vehicle_id=cast(str, vehicle_row.unit_number),
        qr_token=cast(str, token_row.qr_token),
        deployment_status=cast(Any, vehicle_row.qr_deployment_status),
    )


@router.post(
    "/vehicles/bulk-generate-qr",
    response_model=VehicleQrBulkGenerateResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Bulk generate vehicle QR tokens",
)
def bulk_generate_vehicle_qr(
    payload: VehicleQrBulkGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_qr_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    generated: list[VehicleQrGenerateResponse] = []
    skipped: list[str] = []
    for vehicle_id in payload.vehicle_ids:
        vehicle = (
            db.query(OrgVehicleRegistry)
            .filter(
                OrgVehicleRegistry.org_id == org_id,
                OrgVehicleRegistry.unit_number == vehicle_id,
                OrgVehicleRegistry.is_active.is_(True),
            )
            .first()
        )
        if vehicle is None:
            skipped.append(vehicle_id)
            continue
        vehicle_row = cast(Any, vehicle)
        token = (
            db.query(VehicleQrToken)
            .filter(
                VehicleQrToken.org_id == org_id,
                VehicleQrToken.adc_vehicle_id == vehicle_row.unit_number,
                VehicleQrToken.status == "active",
            )
            .first()
        )
        if token is None:
            token = VehicleQrToken(
                qr_token=secrets.token_urlsafe(32),
                org_id=org_id,
                adc_vehicle_id=vehicle_row.unit_number,
                status="active",
            )
            db.add(token)
        vehicle_row.qr_deployment_status = "generated"
        vehicle_row.qr_generated_at_utc = datetime.now(timezone.utc)
        _emit_vehicle_qr_event(
            db,
            org_id=org_id,
            actor_id=cast(uuid.UUID, current_user.id),
            action="vehicle_qr_generated",
            vehicle_id=cast(str, vehicle_row.unit_number),
            payload={"bulk": True},
        )
        generated.append(
            VehicleQrGenerateResponse(
                vehicle_id=cast(str, vehicle_row.unit_number),
                qr_token=cast(str, cast(Any, token).qr_token),
                deployment_status="generated",
            )
        )
    db.commit()
    return VehicleQrBulkGenerateResponse(
        generated_count=len(generated),
        skipped_count=len(skipped),
        generated=generated,
        skipped_vehicle_ids=skipped,
    )


@router.post(
    "/vehicles/{vehicle_id}/rotate-qr",
    response_model=VehicleQrGenerateResponse,
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Rotate active vehicle QR token",
)
def rotate_vehicle_qr(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_qr_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    vehicle = _get_required_vehicle(db, org_id=org_id, vehicle_id=vehicle_id)
    vehicle_row = cast(Any, vehicle)

    active_tokens = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.adc_vehicle_id == vehicle_row.unit_number,
            VehicleQrToken.status == "active",
        )
        .all()
    )
    for row in active_tokens:
        cast(Any, row).status = "rotated"

    token = VehicleQrToken(
        qr_token=secrets.token_urlsafe(32),
        org_id=org_id,
        adc_vehicle_id=vehicle_row.unit_number,
        status="active",
        rotated_from_token=active_tokens[0].qr_token if active_tokens else None,
    )
    db.add(token)
    vehicle_row.qr_deployment_status = "generated"
    vehicle_row.qr_generated_at_utc = datetime.now(timezone.utc)
    _emit_vehicle_qr_event(
        db,
        org_id=org_id,
        actor_id=cast(uuid.UUID, current_user.id),
        action=SystemEventType.VEHICLE_QR_ROTATED.value,
        vehicle_id=cast(str, vehicle_row.unit_number),
        payload={"token_sha256": hashlib.sha256(token.qr_token.encode()).hexdigest()},
    )
    db.commit()
    return VehicleQrGenerateResponse(vehicle_id=cast(str, vehicle_row.unit_number), qr_token=cast(str, cast(Any, token).qr_token), deployment_status="generated")


@router.get(
    "/vehicles/{vehicle_id}/qr/printable",
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Download printable vehicle QR PDF",
)
def download_vehicle_qr_printable(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_qr_access(current_user, write=True)
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    vehicle = _get_required_vehicle(db, org_id=org_id, vehicle_id=vehicle_id)
    vehicle_row = cast(Any, vehicle)

    token = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.adc_vehicle_id == vehicle_row.unit_number,
            VehicleQrToken.status == "active",
        )
        .first()
    )
    if token is None:
        raise_api_error(status_code=404, message="QR token not generated for vehicle.", code="RESOURCE_NOT_FOUND")

    vehicle_row.qr_deployment_status = "distributed"
    vehicle_row.qr_distributed_at_utc = datetime.now(timezone.utc)
    token_row = cast(Any, token)
    pdf_bytes = render_pdf(
        "vehicle_qr_printable",
        {
            "vehicle_id": cast(str, vehicle_row.unit_number),
            "qr_token": cast(str, token_row.qr_token),
            "qr_image_data_uri": qr_png_data_uri(cast(str, token_row.qr_token)),
        },
    )
    _emit_vehicle_qr_event(
        db,
        org_id=org_id,
        actor_id=cast(uuid.UUID, current_user.id),
        action="vehicle_qr_distributed",
        vehicle_id=cast(str, vehicle_row.unit_number),
        payload={"artifact_type": "printable_pdf"},
    )
    db.commit()

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="vehicle-{vehicle_row.unit_number}-qr.pdf"'},
    )


@router.get(
    "/onboarding/qr-stats",
    response_model=VehicleQrStatsResponse,
    responses={403: {"model": ApiErrorResponse}},
    summary="Get QR deployment coverage stats",
)
def get_org_onboarding_qr_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_qr_access(current_user)
    context = build_user_auth_context(db, current_user)
    return _vehicle_qr_stats(db, org_id=_first_org_id(context))
