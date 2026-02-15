"""Twilio Verify service wrapper for OTP verification."""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _verify_url(resource: str) -> str:
    service_sid = settings.TWILIO_VERIFY_SERVICE_SID.strip()
    if not (
        settings.TWILIO_ACCOUNT_SID.strip()
        and settings.TWILIO_AUTH_TOKEN.strip()
        and service_sid
    ):
        raise RuntimeError("Twilio Verify is not configured")
    return f"https://verify.twilio.com/v2/Services/{service_sid}/{resource}"


def _twilio_auth() -> tuple[str, str]:
    return settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN


def start_verification(phone_e164: str) -> str:
    """Start an OTP verification via Twilio Verify and return verification SID."""
    response = httpx.post(
        _verify_url("Verifications"),
        auth=_twilio_auth(),
        data={"To": phone_e164, "Channel": "sms"},
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    sid = payload.get("sid")
    if not isinstance(sid, str) or not sid:
        raise RuntimeError("Twilio Verify response missing sid")
    logger.info("Twilio verification started sid=%s", sid)
    return sid


def check_verification(phone_e164: str, otp: str) -> bool:
    """Check an OTP code against Twilio Verify."""
    response = httpx.post(
        _verify_url("VerificationCheck"),
        auth=_twilio_auth(),
        data={"To": phone_e164, "Code": otp},
        timeout=10.0,
    )
    response.raise_for_status()
    status = response.json().get("status")
    return status == "approved"
