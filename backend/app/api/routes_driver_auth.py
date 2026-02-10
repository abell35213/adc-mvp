"""Driver OTP authentication routes."""

import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverOtpRequest,
    DriverOtpRequestResponse,
    DriverOtpVerifyRequest,
    DriverOtpVerifyResponse,
)
from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import OtpChallenge
from app.db.repo.drivers import (
    OTP_EXPIRY_SECONDS,
    create_otp_challenge,
    get_driver_by_phone,
    get_otp_challenge,
    increment_otp_attempts,
    mark_otp_verified,
)
from app.db.session import get_db
from app.services.phone_normalize import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter()


def _phone_hash(phone_e164: str) -> str:
    """Return a keyed HMAC-SHA256 hex digest of the phone number for audit logs."""
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        phone_e164.encode(),
        hashlib.sha256,
    ).hexdigest()


# ── POST /driver/auth/request-otp ──────────────────────────────────


@router.post("/request-otp", response_model=DriverOtpRequestResponse)
def request_otp(body: DriverOtpRequest, db: Session = Depends(get_db)):
    """Request an OTP code for driver phone verification.

    Always returns ``{detail: "OTP sent"}`` even if the phone is not known,
    to prevent phone-number enumeration.
    """
    try:
        phone_e164 = normalize_phone(body.phone_e164)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid phone number",
        )

    # Try to start Twilio verification; fall back gracefully
    twilio_sid: str | None = None
    try:
        from app.services import twilio_verify

        twilio_sid = twilio_verify.start_verification(phone_e164)
    except Exception:
        logger.warning("Twilio verify start failed for phone hash=%s", _phone_hash(phone_e164))

    challenge = create_otp_challenge(db, phone_e164, twilio_sid=twilio_sid)

    logger.info(
        "DRIVER_OTP_REQUESTED phone_hash=%s challenge=%s",
        _phone_hash(phone_e164),
        challenge.challenge_id,
    )

    return DriverOtpRequestResponse()


# ── POST /driver/auth/verify-otp ──────────────────────────────────


@router.post("/verify-otp", response_model=DriverOtpVerifyResponse)
def verify_otp(body: DriverOtpVerifyRequest, db: Session = Depends(get_db)):
    """Verify an OTP code and issue a driver-scoped JWT on success."""
    try:
        phone_e164 = normalize_phone(body.phone_e164)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid phone number",
        )

    # Find the latest pending challenge for this phone
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
            detail="Challenge not found",
        )

    if challenge.status == "locked":
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Challenge locked due to too many attempts",
        )

    if challenge.status == "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge already verified",
        )

    now = datetime.now(timezone.utc)
    if challenge.expires_at_utc.tzinfo is None:
        expires = challenge.expires_at_utc.replace(tzinfo=timezone.utc)
    else:
        expires = challenge.expires_at_utc
    if now > expires:
        challenge.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Challenge expired",
        )

    # Check OTP via Twilio; on provider failure return 502 without penalising the user
    otp_ok = False
    try:
        from app.services import twilio_verify

        otp_ok = twilio_verify.check_verification(phone_e164, body.otp_code)
    except Exception:
        logger.exception("Twilio verify check failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OTP verification service unavailable, please retry",
        )

    if not otp_ok:
        challenge = increment_otp_attempts(db, challenge)
        logger.info(
            "DRIVER_OTP_FAILED phone_hash=%s attempts=%d status=%s",
            _phone_hash(phone_e164),
            challenge.attempt_count,
            challenge.status,
        )
        if challenge.status == "locked":
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Challenge locked due to too many attempts",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP",
        )

    # OTP verified — find existing driver and issue JWT
    driver = get_driver_by_phone(db, phone_e164)
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No driver registered with this phone number",
        )
    mark_otp_verified(db, challenge)

    token = create_access_token({
        "sub": str(driver.driver_id),
        "scope": "driver",
        "phone": driver.phone_e164,
    })

    logger.info(
        "DRIVER_OTP_VERIFIED phone_hash=%s driver=%s",
        _phone_hash(phone_e164),
        driver.driver_id,
    )

    return DriverOtpVerifyResponse(access_token=token)
