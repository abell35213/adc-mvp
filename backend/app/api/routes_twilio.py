"""Twilio webhook routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import parse_qs
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import settings

router = APIRouter()

VOICE_MESSAGE = (
    "ADC alert. An incident has been reported. Please check the ADC dashboard."
)


def _build_twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    message = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode(), message.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _validate_twilio_request(request: Request, params: dict[str, str]) -> None:
    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Twilio signature",
        )
    if not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio auth token not configured",
        )
    expected = _build_twilio_signature(
        settings.TWILIO_AUTH_TOKEN, str(request.url), params
    )
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature",
        )


def _build_twiml(message: str) -> str:
    response = Element("Response")
    say = SubElement(response, "Say")
    say.text = message
    return f'<?xml version="1.0" encoding="UTF-8"?>{tostring(response, encoding="unicode")}'


@router.post("/voice")
async def twilio_voice_webhook(request: Request):
    body = await request.body()
    params = {key: values[0] for key, values in parse_qs(body.decode()).items()}
    _validate_twilio_request(request, params)
    return Response(
        content=_build_twiml(VOICE_MESSAGE),
        media_type="application/xml",
    )
