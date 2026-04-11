"""Backward-compatible Twilio webhook module using shared webhook framework."""

from app.api.routes.routes_webhooks import VOICE_MESSAGE, router
from app.integrations.webhooks.signatures import (
    build_twilio_signature as _build_twilio_signature,
)

__all__ = ["router", "VOICE_MESSAGE", "_build_twilio_signature"]
