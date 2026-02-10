"""Twilio Verify service wrapper for OTP verification."""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Lazy-initialise the Twilio REST client."""
    from twilio.rest import Client  # type: ignore[import-untyped]

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def start_verification(phone_e164: str) -> str:
    """Start an OTP verification via Twilio Verify.

    Returns the verification SID.
    """
    client = _get_client()
    verification = client.verify.v2.services(
        settings.TWILIO_VERIFY_SERVICE_SID
    ).verifications.create(to=phone_e164, channel="sms")
    logger.info("Twilio verification started sid=%s", verification.sid)
    return verification.sid


def check_verification(phone_e164: str, otp: str) -> bool:
    """Check an OTP code against Twilio Verify.

    Returns True if the code is approved, False otherwise.
    """
    client = _get_client()
    check = client.verify.v2.services(
        settings.TWILIO_VERIFY_SERVICE_SID
    ).verification_checks.create(to=phone_e164, code=otp)
    return check.status == "approved"
