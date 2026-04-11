"""Twilio Verify service wrapper backed by integration providers."""

from __future__ import annotations

from app.integrations.service import get_verify_provider


def start_verification(phone_e164: str) -> str:
    return get_verify_provider().start_verification(phone_e164)


def check_verification(phone_e164: str, otp: str) -> bool:
    return get_verify_provider().check_verification(phone_e164, otp)
