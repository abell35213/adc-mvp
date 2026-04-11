"""Shared provider webhook routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import MetricNames, increment, timed
from app.db.session import get_db
from app.integrations.webhooks.handlers import (
    persist_twilio_voice_callback,
    process_twilio_status_callback,
)
from app.integrations.webhooks.signatures import (
    parse_form_encoded_body,
    validate_twilio_signature,
)
from app.services.twilio_notify import build_voice_twiml

logger = logging.getLogger(__name__)

router = APIRouter()

VOICE_MESSAGE = (
    "ADC alert. An incident has been reported. Please check the ADC dashboard."
)


@router.post("/voice")
async def twilio_voice_webhook(request: Request, db: Session = Depends(get_db)):
    increment(MetricNames.TWILIO_WEBHOOK_ATTEMPTS)
    with timed(MetricNames.TWILIO_WEBHOOK_ATTEMPTS):
        raw_body = await request.body()
        params = parse_form_encoded_body(raw_body)
        signature_valid, signature_error = validate_twilio_signature(
            auth_token=settings.TWILIO_AUTH_TOKEN,
            request_url=str(request.url),
            params=params,
            provided_signature=request.headers.get("X-Twilio-Signature"),
        )
        result = persist_twilio_voice_callback(
            db,
            payload=params,
            raw_payload=raw_body.decode("utf-8", errors="ignore"),
            signature_valid=signature_valid,
            signature_error=signature_error,
        )
        if result.status_code != 200:
            increment(MetricNames.TWILIO_WEBHOOK_FAILURES)
            logger.warning("Twilio webhook signature validation failed")
            return Response(status_code=result.status_code, content=result.body["detail"])

    return Response(
        content=build_voice_twiml(VOICE_MESSAGE),
        media_type="application/xml",
    )


@router.post("/status")
async def twilio_status_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    params = parse_form_encoded_body(raw_body)
    signature_valid, signature_error = validate_twilio_signature(
        auth_token=settings.TWILIO_AUTH_TOKEN,
        request_url=str(request.url),
        params=params,
        provided_signature=request.headers.get("X-Twilio-Signature"),
    )
    result = process_twilio_status_callback(
        db,
        payload=params,
        raw_payload=raw_body.decode("utf-8", errors="ignore"),
        signature_valid=signature_valid,
        signature_error=signature_error,
    )
    if result.status_code == 403:
        return Response(status_code=403, content=result.body["detail"])
    return result.body
