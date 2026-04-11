"""Twilio notification helpers backed by integration providers."""

from __future__ import annotations

from app.integrations.errors import IntegrationError, map_twilio_error
from app.integrations.service import get_messaging_provider, get_voice_provider


def send_sms(to: str, message: str) -> str:
    try:
        return get_messaging_provider().send_sms(to=to, message=message)
    except Exception as exc:
        raise IntegrationError(map_twilio_error(exc, category="messaging")) from exc


def place_call(to: str, twiml_content: str) -> str:
    try:
        return get_voice_provider().place_call(to=to, twiml_content=twiml_content)
    except Exception as exc:
        raise IntegrationError(map_twilio_error(exc, category="messaging")) from exc


def build_voice_twiml(message: str) -> str:
    return get_voice_provider().build_voice_twiml(message=message)
