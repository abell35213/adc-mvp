"""Driver OTP authentication routes."""

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    RequestOtpRequest,
    RequestOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.core.security import create_access_token
from app.db.repo.drivers import (
    OTP_EXPIRY_SECONDS,
    create_otp_challenge,
    find_or_create_driver,
    get_otp_challenge,
    increment_otp_attempts,
    mark_otp_verified,
)
from app.db.session import get_db
from app.services.phone_normalize import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter()


def _phone_hash(phone_e164: str) -> str:
    """Return a SHA-256 hex digest of the phone number for audit logs."""
    return hashlib.sha256(phone_e164.encode()).hexdigest()


# ── POST /driver/auth/request-otp ──────────────────────────────────


@router.post("/request-otp", response_model=RequestOtpResponse)
def request_otp(body: RequestOtpRequest, db: Session = Depends(get_db)):
    """Request an OTP code for driver phone verification.

    Always returns ``{ok: true}`` even if the phone is not known,
    to prevent phone-number enumeration.
    """
    try:
        phone_e164 = normalize_phone(body.phone)
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
        challenge.id,
    )

    return RequestOtpResponse(
        ok=True,
        challenge_id=challenge.id,
        expires_in_seconds=OTP_EXPIRY_SECONDS,
    )


# ── POST /driver/auth/verify-otp ──────────────────────────────────


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(body: VerifyOtpRequest, db: Session = Depends(get_db)):
    """Verify an OTP code and issue a driver-scoped JWT on success."""
    challenge = get_otp_challenge(db, body.challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    if challenge.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Challenge locked due to too many attempts",
        )

    if challenge.is_verified:
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
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Challenge expired",
        )

    # Check OTP via Twilio (or accept in dev if Twilio is not configured)
    otp_ok = False
    try:
        from app.services import twilio_verify

        otp_ok = twilio_verify.check_verification(challenge.phone_e164, body.otp)
    except Exception:
        logger.warning("Twilio verify check failed, rejecting OTP")

    if not otp_ok:
        challenge = increment_otp_attempts(db, challenge)
        logger.info(
            "DRIVER_OTP_FAILED phone_hash=%s attempts=%d locked=%s",
            _phone_hash(challenge.phone_e164),
            challenge.attempt_count,
            challenge.is_locked,
        )
        detail = "Invalid OTP"
        if challenge.is_locked:
            detail = "Challenge locked due to too many attempts"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    # OTP verified — find/create driver and issue JWT
    driver = find_or_create_driver(db, challenge.phone_e164)
    mark_otp_verified(db, challenge)

    token = create_access_token({
        "sub": str(driver.id),
        "scope": "driver",
        "phone": driver.phone_e164,
    })

    logger.info(
        "DRIVER_OTP_VERIFIED phone_hash=%s driver=%s",
        _phone_hash(challenge.phone_e164),
        driver.id,
    )

    return VerifyOtpResponse(
        access_token=token,
        driver_id=driver.id,
    )
