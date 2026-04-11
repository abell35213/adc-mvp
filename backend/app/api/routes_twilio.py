"""Twilio webhook routes."""

from __future__ import annotations

import base64
import logging
import hashlib
import hmac
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import MetricNames, increment, timed
from app.db.repo.message_operations import (
    get_message_operation_by_provider_message_id,
    update_message_operation_status,
)
from app.db.repo.provider_webhook_events import create_provider_webhook_event
from app.db.session import get_db
from app.services.twilio_notify import build_voice_twiml

logger = logging.getLogger(__name__)

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
    increment(MetricNames.TWILIO_WEBHOOK_ATTEMPTS)
    with timed(MetricNames.TWILIO_WEBHOOK_ATTEMPTS):
        body = await request.body()
        raw_params = parse_qs(body.decode(), keep_blank_values=True)
        params = _flatten_twilio_params(raw_params)
        try:
            _validate_twilio_request(request, params)
        except HTTPException:
            increment(MetricNames.TWILIO_WEBHOOK_FAILURES)
            logger.warning("Twilio webhook signature validation failed")
            raise
    return Response(
        content=build_voice_twiml(VOICE_MESSAGE),
        media_type="application/xml",
    )


@router.post("/status")
async def twilio_status_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    raw_params = parse_qs(body.decode(), keep_blank_values=True)
    params = _flatten_twilio_params(raw_params)
    _validate_twilio_request(request, params)
    create_provider_webhook_event(
        db,
        org_id=None,
        provider="twilio",
        domain="messaging",
        event_type="status_callback",
        status="processed",
        external_reference=params.get("MessageSid"),
        payload_json=params,
    )
    message_sid = params.get("MessageSid")
    message_status = (params.get("MessageStatus") or "").strip().lower()
    error_code = params.get("ErrorCode") or None
    if message_sid:
        operation = get_message_operation_by_provider_message_id(
            db, provider="twilio", provider_message_id=message_sid
        )
        if operation is not None:
            status_map = {
                "queued": "queued",
                "sent": "sent",
                "delivered": "delivered",
                "undelivered": "undelivered",
                "failed": "failed",
            }
            mapped = status_map.get(message_status)
            if mapped:
                update_message_operation_status(
                    db,
                    operation,
                    to_status=mapped,
                    normalized_error_code=f"TWILIO_{error_code}" if error_code else None,
                    details_json=params,
                )
    return {"status": "ok"}
