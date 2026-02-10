"""Repository layer for drivers and OTP challenges."""

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Driver, OtpChallenge

OTP_EXPIRY_SECONDS = 300  # 5 minutes
MAX_OTP_ATTEMPTS = 5


# ── Drivers ────────────────────────────────────────────────────────


def get_driver_by_phone(db: Session, phone_e164: str) -> Driver | None:
    return db.query(Driver).filter(Driver.phone_e164 == phone_e164).first()


def get_driver_by_id(db: Session, driver_id: _uuid.UUID) -> Driver | None:
    return db.query(Driver).filter(Driver.driver_id == driver_id).first()


def find_or_create_driver(db: Session, phone_e164: str) -> Driver:
    """Return existing driver or create a new one for the given phone."""
    driver = get_driver_by_phone(db, phone_e164)
    if driver is None:
        driver = Driver(phone_e164=phone_e164)
        db.add(driver)
        db.commit()
        db.refresh(driver)
    return driver


# ── OTP Challenges ─────────────────────────────────────────────────


def create_otp_challenge(
    db: Session,
    phone_e164: str,
    twilio_sid: str | None = None,
) -> OtpChallenge:
    """Create a new OTP challenge row."""
    challenge = OtpChallenge(
        phone_e164=phone_e164,
        twilio_sid=twilio_sid,
        expires_at_utc=datetime.now(timezone.utc) + timedelta(seconds=OTP_EXPIRY_SECONDS),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def get_otp_challenge(db: Session, challenge_id: _uuid.UUID) -> OtpChallenge | None:
    return db.query(OtpChallenge).filter(OtpChallenge.id == challenge_id).first()


def increment_otp_attempts(db: Session, challenge: OtpChallenge) -> OtpChallenge:
    """Increment attempt count and lock if too many attempts."""
    challenge.attempt_count += 1
    if challenge.attempt_count >= MAX_OTP_ATTEMPTS:
        challenge.is_locked = True
    db.commit()
    db.refresh(challenge)
    return challenge


def mark_otp_verified(db: Session, challenge: OtpChallenge) -> OtpChallenge:
    """Mark an OTP challenge as verified."""
    challenge.is_verified = True
    db.commit()
    db.refresh(challenge)
    return challenge
