"""Driver API routes — driver auth, profile, and QR vehicle resolution."""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverMeResponse,
    DriverOtpRequest,
    DriverOtpRequestResponse,
    DriverOtpVerifyRequest,
    DriverOtpVerifyResponse,
    ResolveQrRequest,
    ResolveQrResponse,
    VehicleInfo,
)
from app.core.security import create_access_token, decode_access_token
from app.db.models import Driver, DriverVehicleAssignment, Event, Org, OtpChallenge, VehicleQrToken
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def _get_current_driver(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Decode driver JWT and return active driver."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not authenticated",
        )

    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    driver_id = payload.get("sub")
    if driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    try:
        driver_uuid = uuid.UUID(driver_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    driver = (
        db.query(Driver)
        .filter(
            Driver.driver_id == driver_uuid,
            Driver.is_active.is_(True),
        )
        .first()
    )
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not found or inactive",
        )
    return driver


def _get_or_create_default_org(db: Session) -> Org:
    org = db.query(Org).order_by(Org.name).first()
    if org is None:
        org = Org(name="Default")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post("/auth/request-otp", response_model=DriverOtpRequestResponse)
def request_driver_otp(body: DriverOtpRequest, db: Session = Depends(get_db)):
    phone_e164 = body.phone_e164.strip()
    if not phone_e164:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required",
        )

    org = _get_or_create_default_org(db)
    driver = db.query(Driver).filter(Driver.phone_e164 == phone_e164).first()
    if driver is None:
        driver = Driver(
            org_id=org.id,
            phone_e164=phone_e164,
            display_name=phone_e164,
        )
        db.add(driver)
        db.commit()
        db.refresh(driver)

    pending = (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.phone_e164 == phone_e164,
            OtpChallenge.status == "pending",
        )
        .all()
    )
    for challenge in pending:
        challenge.status = "expired"

    now = datetime.now(timezone.utc)
    otp = OtpChallenge(
        phone_e164=phone_e164,
        expires_at_utc=now + timedelta(minutes=10),
        last_sent_at_utc=now,
    )
    db.add(otp)
    db.commit()

    logger.info("OTP challenge requested for driver=%s", phone_e164)
    return DriverOtpRequestResponse()


@router.post("/auth/verify-otp", response_model=DriverOtpVerifyResponse)
def verify_driver_otp(body: DriverOtpVerifyRequest, db: Session = Depends(get_db)):
    phone_e164 = body.phone_e164.strip()
    otp_code = body.otp_code.strip()
    if not phone_e164 or not otp_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number and OTP code are required",
        )

    challenge = (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.phone_e164 == phone_e164,
            OtpChallenge.status == "pending",
        )
        .order_by(OtpChallenge.created_at_utc.desc())
        .first()
    )
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTP challenge not found",
        )

    now = datetime.now(timezone.utc)
    if _as_utc(challenge.expires_at_utc) < now:
        challenge.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired",
        )

    challenge.attempt_count += 1
    challenge.status = "verified"
    db.commit()

    driver = db.query(Driver).filter(Driver.phone_e164 == phone_e164).first()
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found",
        )

    token = create_access_token({"sub": str(driver.driver_id), "role": "driver"})
    return DriverOtpVerifyResponse(access_token=token)


@router.get("/me", response_model=DriverMeResponse)
def driver_me(
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Return the authenticated driver profile and current vehicle (if any)."""
    assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver.driver_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        )
        .first()
    )

    vehicle = None
    if assignment is not None:
        vehicle = VehicleInfo(
            adc_vehicle_id=assignment.adc_vehicle_id,
            display_label=assignment.adc_vehicle_id,
        )

    return DriverMeResponse(
        driver_id=driver.driver_id,
        org_id=driver.org_id,
        phone_e164=driver.phone_e164,
        display_name=driver.display_name,
        vehicle=vehicle,
    )


@router.post("/vehicle/resolve-qr", response_model=ResolveQrResponse)
def resolve_qr(
    body: ResolveQrRequest,
    _driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Resolve a QR token to a vehicle. Only active tokens are accepted."""
    token_row = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.qr_token == body.qr_token,
            VehicleQrToken.status == "active",
        )
        .first()
    )

    if token_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR token not found or inactive",
        )

    # Emit DRIVER_VEHICLE_RESOLVED event — store sha256(token), not raw
    token_hash = hashlib.sha256(body.qr_token.encode()).hexdigest()

    event = Event(
        org_id=token_row.org_id,
        incident_id=None,
        event_type=SystemEventType.DRIVER_VEHICLE_RESOLVED.value,
        actor_type="driver_app",
        actor_id="anonymous",
        payload={
            "adc_vehicle_id": token_row.adc_vehicle_id,
            "token_sha256": token_hash,
        },
    )
    db.add(event)
    db.commit()

    logger.info(
        "DRIVER_VEHICLE_RESOLVED vehicle=%s token_sha256=%s",
        token_row.adc_vehicle_id,
        token_hash,
    )

    return ResolveQrResponse(
        adc_vehicle_id=token_row.adc_vehicle_id,
        display_label=token_row.adc_vehicle_id,
    )
