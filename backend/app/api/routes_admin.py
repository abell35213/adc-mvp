"""Admin API routes — vehicle QR token management."""

import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import QrPayloadResponse, RotateQrResponse
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.models import Event, User, VehicleQrToken
from app.db.session import get_db
from app.db.repo.users import get_user_org_ids
from app.domain.system_event_types import SystemEventType

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the authenticated user has the admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


@router.post(
    "/vehicles/{vehicle_id}/qr/rotate",
    response_model=RotateQrResponse,
    status_code=201,
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

    # Generate a new 32-byte base64url token
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


@router.get("/vehicles/{vehicle_id}/qr", response_model=QrPayloadResponse)
def get_qr_payload(
    vehicle_id: str,
    admin: User = Depends(_require_admin),
):
    """Return the deep link string for QR code generation."""
    scheme = settings.DRIVER_APP_DEEPLINK_SCHEME
    deep_link = f"{scheme}://vehicle/{vehicle_id}"
    return QrPayloadResponse(deep_link=deep_link)
