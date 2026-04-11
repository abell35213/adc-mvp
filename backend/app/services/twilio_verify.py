"""Twilio Verify service wrapper backed by integration providers."""

from __future__ import annotations

from app.integrations.errors import IntegrationError, map_twilio_error
from app.integrations.service import get_verify_provider


def start_verification(phone_e164: str) -> str:
    try:
        return get_verify_provider().start_verification(phone_e164)
    except Exception as exc:
        raise IntegrationError(map_twilio_error(exc, category="auth")) from exc


def check_verification(phone_e164: str, otp: str) -> bool:
    try:
        return get_verify_provider().check_verification(phone_e164, otp)
    except Exception as exc:
        raise IntegrationError(map_twilio_error(exc, category="auth")) from exc
