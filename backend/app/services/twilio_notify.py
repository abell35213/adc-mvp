"""Twilio notification helpers."""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/Accounts"


def _require_setting(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} is not configured")
    return value


def _twilio_auth() -> tuple[str, str]:
    account_sid = _require_setting("TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID)
    auth_token = _require_setting("TWILIO_AUTH_TOKEN", settings.TWILIO_AUTH_TOKEN)
    return account_sid, auth_token


def _twilio_url(path: str) -> str:
    account_sid = _require_setting("TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID)
    return f"{TWILIO_API_BASE}/{account_sid}/{path}"


def _post_twilio(path: str, data: dict[str, str]) -> dict[str, Any]:
    url = _twilio_url(path)
    account_sid, auth_token = _twilio_auth()
    with httpx.Client() as client:
        response = client.post(
            url,
            data=data,
            auth=(account_sid, auth_token),
            timeout=10.0,
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Twilio response payload")
    return payload


def send_sms(to: str, message: str) -> str:
    """Send an SMS message and return the Twilio message SID."""
    from_number = _require_setting("TWILIO_SMS_FROM", settings.TWILIO_SMS_FROM)
    payload = _post_twilio(
        "Messages.json",
        {
            "To": to,
            "From": from_number,
            "Body": message,
        },
    )
    sid = payload.get("sid")
    if not sid:
        raise ValueError("Twilio SMS response missing SID")
    return sid


def place_call(to: str, twiml_url_or_twiml: str) -> str:
    """Place a voice call and return the Twilio call SID."""
    from_number = _require_setting("TWILIO_VOICE_FROM", settings.TWILIO_VOICE_FROM)
    data = {
        "To": to,
        "From": from_number,
    }
    stripped_value = twiml_url_or_twiml.lstrip()
    if stripped_value.startswith(("http://", "https://")):
        data["Url"] = stripped_value
    else:
        data["Twiml"] = twiml_url_or_twiml
    payload = _post_twilio("Calls.json", data)
    sid = payload.get("sid")
    if not sid:
        raise ValueError("Twilio call response missing SID")
    return sid


def build_voice_twiml(message: str) -> str:
    """Build a TwiML payload that speaks a single message."""
    response = Element("Response")
    say = SubElement(response, "Say")
    say.text = message
    return f'<?xml version="1.0" encoding="UTF-8"?>{tostring(response, encoding="unicode")}'
