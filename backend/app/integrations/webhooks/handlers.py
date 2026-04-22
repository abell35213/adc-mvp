"""Shared webhook handlers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.metrics import MetricNames, increment
from app.db.repo.message_operations import (
    get_message_operation_by_provider_message_id,
    update_message_operation_status,
)
from app.db.repo.provider_webhook_events import (
    create_provider_webhook_event,
    get_provider_webhook_event_by_idempotency_key,
    update_provider_webhook_event,
)
from app.observability.redaction import redact_payload_for_storage, redact_raw_payload


@dataclass
class WebhookResult:
    status_code: int
    body: dict[str, str]


def build_idempotency_key(
    *,
    provider: str,
    event_type: str,
    external_reference: str | None,
    payload: dict[str, str],
) -> str:
    status = payload.get("MessageStatus", "")
    seed = f"{provider}|{event_type}|{external_reference or ''}|{status}|{sorted(payload.items())}"
    return hashlib.sha256(seed.encode()).hexdigest()


def process_twilio_status_callback(
    db: Session,
    *,
    payload: dict[str, str],
    raw_payload: str,
    signature_valid: bool,
    signature_error: str | None,
) -> WebhookResult:
    increment(MetricNames.TWILIO_WEBHOOK_ATTEMPTS)
    sanitized_payload = redact_payload_for_storage(payload)
    sanitized_raw_payload = redact_raw_payload(raw_payload)
    message_sid = payload.get("MessageSid")
    idempotency_key = build_idempotency_key(
        provider="twilio",
        event_type="status_callback",
        external_reference=message_sid,
        payload=payload,
    )

    if not signature_valid:
        create_provider_webhook_event(
            db,
            org_id=None,
            provider="twilio",
            domain="messaging",
            event_type="status_callback",
            status="failed",
            external_reference=message_sid,
            idempotency_key=idempotency_key,
            signature_valid=False,
            processing_outcome="invalid_signature",
            raw_payload=raw_payload,
            payload_json=payload,
            error_message="twilio_signature_validation_failed",
            error_details_json={"reason": signature_error or "invalid_signature"},
        )
        return WebhookResult(status_code=403, body={"detail": "Invalid Twilio signature"})

    existing = get_provider_webhook_event_by_idempotency_key(
        db,
        provider="twilio",
        event_type="status_callback",
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        create_provider_webhook_event(
            db,
            org_id=None,
            provider="twilio",
            domain="messaging",
            event_type="status_callback",
            status="ignored",
            external_reference=message_sid,
            idempotency_key=idempotency_key,
            signature_valid=signature_valid,
            processing_outcome="duplicate",
            raw_payload=sanitized_raw_payload,
            payload_json=sanitized_payload,
            error_message="duplicate_webhook",
            error_details_json={"duplicate_of": str(existing.webhook_event_id)},
        )
        increment("webhook.twilio.duplicate")
        return WebhookResult(status_code=200, body={"status": "duplicate"})

    event = create_provider_webhook_event(
        db,
        org_id=None,
        provider="twilio",
        domain="messaging",
        event_type="status_callback",
        status="received",
        external_reference=message_sid,
        idempotency_key=idempotency_key,
        signature_valid=signature_valid,
        raw_payload=sanitized_raw_payload,
        payload_json=sanitized_payload,
    )

    message_status = (payload.get("MessageStatus") or "").strip().lower()
    error_code = payload.get("ErrorCode") or None

    operation = None
    if message_sid:
        operation = get_message_operation_by_provider_message_id(
            db, provider="twilio", provider_message_id=message_sid
        )

    if operation is None:
        increment("webhook.twilio.orphaned")
        update_provider_webhook_event(
            db,
            event,
            status="ignored",
            processing_outcome="operation_not_found",
            error_message="message_operation_not_found",
            error_details_json={"provider_message_id": message_sid},
        )
        return WebhookResult(status_code=200, body={"status": "ok"})

    status_map = {
        "queued": "queued",
        "sent": "sent",
        "delivered": "delivered",
        "undelivered": "undelivered",
        "failed": "failed",
    }
    mapped = status_map.get(message_status)
    if mapped is None:
        increment("webhook.twilio.unsupported_status")
        update_provider_webhook_event(
            db,
            event,
            status="ignored",
            processing_outcome="unsupported_status",
            error_message="unsupported_message_status",
            error_details_json={"message_status": message_status},
        )
        return WebhookResult(status_code=200, body={"status": "ok"})

    update_message_operation_status(
        db,
        operation,
        to_status=mapped,
        normalized_error_code=f"TWILIO_{error_code}" if error_code else None,
        details_json=sanitized_payload,
    )
    if mapped in {"failed", "undelivered"}:
        increment(MetricNames.OTP_DELIVERY_FAILURE)
    if mapped == "delivered":
        increment(MetricNames.OTP_DELIVERY_SUCCESS)
    update_provider_webhook_event(
        db,
        event,
        status="processed",
        processing_outcome="message_operation_updated",
        error_details_json={},
    )
    return WebhookResult(status_code=200, body={"status": "ok"})


def persist_twilio_voice_callback(
    db: Session,
    *,
    payload: dict[str, str],
    raw_payload: str,
    signature_valid: bool,
    signature_error: str | None,
) -> WebhookResult:
    increment(MetricNames.TWILIO_WEBHOOK_ATTEMPTS)
    sanitized_payload = redact_payload_for_storage(payload)
    sanitized_raw_payload = redact_raw_payload(raw_payload)
    idempotency_key = build_idempotency_key(
        provider="twilio",
        event_type="voice_callback",
        external_reference=payload.get("CallSid"),
        payload=payload,
    )
    outcome = "accepted" if signature_valid else "invalid_signature"
    status = "processed" if signature_valid else "failed"
    create_provider_webhook_event(
        db,
        org_id=None,
        provider="twilio",
        domain="voice",
        event_type="voice_callback",
        status=status,
        external_reference=payload.get("CallSid"),
        idempotency_key=idempotency_key,
        signature_valid=signature_valid,
        processing_outcome=outcome,
        raw_payload=sanitized_raw_payload,
        payload_json=sanitized_payload,
        error_message=None if signature_valid else "twilio_signature_validation_failed",
        error_details_json={} if signature_valid else {"reason": signature_error},
    )
    if signature_valid:
        return WebhookResult(status_code=200, body={"status": "ok"})
    increment(MetricNames.WEBHOOK_SIGNATURE_FAILURES)
    increment(MetricNames.TWILIO_WEBHOOK_FAILURES)
    return WebhookResult(status_code=403, body={"detail": "Invalid Twilio signature"})
