"""Twilio webhook routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import settings
from app.services.twilio_notify import build_voice_twiml

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


def _flatten_twilio_params(raw_params: dict[str, list[str]]) -> dict[str, str]:
    """Flatten Twilio params to string values for signature validation.

    If Twilio sends multiple values for a key, they are joined with commas.
    """
    params = {}
    for key, values in raw_params.items():
        if not values:
            params[key] = ""
        elif len(values) == 1:
            params[key] = values[0]
        else:
            params[key] = ",".join(values)
    return params


@router.post("/voice")
async def twilio_voice_webhook(request: Request):
    body = await request.body()
    raw_params = parse_qs(body.decode(), keep_blank_values=True)
    params = _flatten_twilio_params(raw_params)
    _validate_twilio_request(request, params)
    return Response(
        content=build_voice_twiml(VOICE_MESSAGE),
        media_type="application/xml",
    )
