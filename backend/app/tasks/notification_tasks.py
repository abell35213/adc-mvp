"""Notification tasks for safety manager alerts."""

from __future__ import annotations

import uuid as _uuid

import httpx

from app.core.metrics import MetricNames, increment
from app.integrations.errors import IntegrationError, as_normalized_error
from app.tasks.celery_app import celery_app


SMS_TEMPLATE = (
    "ADC alert: Incident {incident_id} reported for vehicle {vehicle_id}. "
    "Severity: {severity}."
)
VOICE_TEMPLATE = (
    "ADC alert. Incident {incident_id} reported for vehicle {vehicle_id}. "
    "Severity {severity}. Please check the ADC dashboard."
)
PHONE_MISSING_MESSAGE = "Safety manager phone number not configured. Please configure a phone number in organization settings."


def _get_db():
    """Return a new database session (non-generator helper for tasks)."""
    from app.db.session import SessionLocal

    return SessionLocal()


def _emit(db, incident_id, event_type, payload=None):
    """Append an event to the append-only log."""
    from app.db.repo.events import create_event

    return create_event(
        db,
        incident_id=incident_id,
        event_type=event_type,
        actor_type="system",
        actor_id="celery",
        payload=payload,
    )


def _idempotency_key(*parts: str | None) -> str:
    normalized = [p or "none" for p in parts]
    return "|".join(normalized)


def _event_exists(db, incident_id, event_type: str, idempotency_key: str) -> bool:
    from app.db.repo.events import get_events_by_incident

    events = get_events_by_incident(db, incident_id)
    return any(
        ev.event_type == event_type
        and isinstance(ev.payload, dict)
        and ev.payload.get("idempotency_key") == idempotency_key
        for ev in events
    )


def _emit_once(db, incident_id, event_type, idempotency_key: str, payload=None):
    full_payload = {"idempotency_key": idempotency_key, **(payload or {})}
    if _event_exists(db, incident_id, event_type, idempotency_key):
        return None
    return _emit(db, incident_id, event_type, full_payload)


def _format_value(value: str | None, fallback: str) -> str:
    return value or fallback


def _compose_sms(incident) -> str:
    return SMS_TEMPLATE.format(
        incident_id=str(incident.incident_id),
        vehicle_id=_format_value(incident.adc_vehicle_id, "unknown"),
        severity=_format_value(incident.severity, "unknown"),
    )


def _compose_voice(incident) -> str:
    return VOICE_TEMPLATE.format(
        incident_id=str(incident.incident_id),
        vehicle_id=_format_value(incident.adc_vehicle_id, "unknown"),
        severity=_format_value(incident.severity, "unknown"),
    )


@celery_app.task(
    bind=True,
    acks_late=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def notify_safety_manager(self, incident_id: str):
    """Notify the safety manager via SMS and/or voice call."""
    increment("notifications.safety_manager.attempts")
    from app.db.models import Org
    from app.db.repo.incidents import get_incident
    from app.db.repo.message_operations import create_message_operation, update_message_operation_status
    from app.domain.system_event_types import SystemEventType
    from app.services.twilio_notify import build_voice_twiml, place_call, send_sms

    inc_uuid = _uuid.UUID(incident_id)
    workflow_key = _idempotency_key("notify_safety_manager", incident_id)
    db = _get_db()

    try:
        incident = get_incident(db, inc_uuid)
        if incident is None:
            raise ValueError(f"Incident {incident_id} not found")
        if incident.org_id is None:
            raise ValueError(f"Incident {incident_id} missing org_id")

        org = db.query(Org).filter(Org.id == incident.org_id).first()
        if org is None:
            raise ValueError(f"Org {incident.org_id} not found")

        if not org.sms_enabled and not org.voice_enabled:
            return {"incident_id": incident_id, "status": "skipped"}

        phone = org.safety_manager_phone
        if not phone:
            reason = PHONE_MISSING_MESSAGE
            if org.sms_enabled:
                _emit_once(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_SMS_FAILED,
                    f"{workflow_key}:sms_failed",
                    {
                        "phone": None,
                        "reason": reason,
                    },
                )
            if org.voice_enabled:
                _emit_once(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_CALL_FAILED,
                    f"{workflow_key}:call_failed",
                    {
                        "phone": None,
                        "reason": reason,
                    },
                )
            raise ValueError(reason)

        message = _compose_sms(incident)
        twiml = build_voice_twiml(_compose_voice(incident))
        errors = []
        result = {
            "incident_id": incident_id,
            "idempotency_key": workflow_key,
        }

        if org.sms_enabled:
            sms_operation = create_message_operation(
                db,
                org_id=incident.org_id,
                incident_id=inc_uuid,
                provider="twilio",
                domain="messaging",
                purpose="safety_manager_sms_notification",
                to_e164=phone,
                status="queued",
                payload_json={"task": "notify_safety_manager"},
            )
            sms_event_key = f"{workflow_key}:sms_sent"
            if _event_exists(
                db, inc_uuid, SystemEventType.SAFETY_MANAGER_SMS_SENT, sms_event_key
            ):
                result["sms_status"] = "already_sent"
                update_message_operation_status(
                    db,
                    sms_operation,
                    to_status="sent",
                    details_json={"reason": "already_sent_event_exists"},
                )
            else:
                try:
                    sms_sid = send_sms(phone, message)
                    result["sms_sid"] = sms_sid
                    update_message_operation_status(
                        db,
                        sms_operation,
                        to_status="sent",
                        provider_message_id=sms_sid,
                        details_json={"sms_sid": sms_sid},
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.SAFETY_MANAGER_SMS_SENT,
                        sms_event_key,
                        {
                            "phone": phone,
                            "sms_sid": sms_sid,
                        },
                    )
                except (httpx.HTTPError, ValueError, IntegrationError) as exc:
                    normalized_error = as_normalized_error(
                        exc, provider_hint="twilio", category="messaging"
                    )
                    update_message_operation_status(
                        db,
                        sms_operation,
                        to_status="failed",
                        normalized_error_code=normalized_error.code,
                        details_json={"reason": normalized_error.operator_message},
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.SAFETY_MANAGER_SMS_FAILED,
                        f"{workflow_key}:sms_failed",
                        {
                            "phone": phone,
                            "reason": normalized_error.user_facing_message,
                            "error_code": normalized_error.code,
                            "retryable": normalized_error.retryable,
                        },
                    )
                    errors.append(f"SMS failed: {normalized_error.operator_message}")

        if org.voice_enabled:
            call_operation = create_message_operation(
                db,
                org_id=incident.org_id,
                incident_id=inc_uuid,
                provider="twilio",
                domain="voice",
                purpose="safety_manager_voice_notification",
                to_e164=phone,
                status="queued",
                payload_json={"task": "notify_safety_manager"},
            )
            call_event_key = f"{workflow_key}:call_placed"
            if _event_exists(
                db, inc_uuid, SystemEventType.SAFETY_MANAGER_CALL_PLACED, call_event_key
            ):
                result["call_status"] = "already_placed"
                update_message_operation_status(
                    db,
                    call_operation,
                    to_status="sent",
                    details_json={"reason": "already_placed_event_exists"},
                )
            else:
                try:
                    call_sid = place_call(phone, twiml)
                    result["call_sid"] = call_sid
                    update_message_operation_status(
                        db,
                        call_operation,
                        to_status="sent",
                        provider_message_id=call_sid,
                        details_json={"call_sid": call_sid},
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.SAFETY_MANAGER_CALL_PLACED,
                        call_event_key,
                        {
                            "phone": phone,
                            "call_sid": call_sid,
                        },
                    )
                except (httpx.HTTPError, ValueError, IntegrationError) as exc:
                    normalized_error = as_normalized_error(
                        exc, provider_hint="twilio", category="messaging"
                    )
                    update_message_operation_status(
                        db,
                        call_operation,
                        to_status="failed",
                        normalized_error_code=normalized_error.code,
                        details_json={"reason": normalized_error.operator_message},
                    )
                    _emit_once(
                        db,
                        inc_uuid,
                        SystemEventType.SAFETY_MANAGER_CALL_FAILED,
                        f"{workflow_key}:call_failed",
                        {
                            "phone": phone,
                            "reason": normalized_error.user_facing_message,
                            "error_code": normalized_error.code,
                            "retryable": normalized_error.retryable,
                        },
                    )
                    errors.append(f"Call failed: {normalized_error.operator_message}")

        if errors:
            raise RuntimeError(f"Notification failures: {'; '.join(errors)}")

        if result.get("sms_status") == "already_sent" and result.get(
            "call_status"
        ) == "already_placed":
            result["status"] = "skipped_duplicate"
        else:
            result["status"] = "notified"

        return result

    except Exception:
        increment(MetricNames.CELERY_TASK_FAILURES)
        raise
    finally:
        db.close()
