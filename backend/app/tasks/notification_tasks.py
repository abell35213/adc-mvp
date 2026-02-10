"""Notification tasks for safety manager alerts."""

from __future__ import annotations

import uuid as _uuid

import httpx

from app.tasks.celery_app import celery_app


SMS_TEMPLATE = (
    "ADC alert: Incident {incident_id} reported for vehicle {vehicle_id}. "
    "Severity: {severity}."
)
VOICE_TEMPLATE = (
    "ADC alert. Incident {incident_id} reported for vehicle {vehicle_id}. "
    "Severity {severity}. Please check the ADC dashboard."
)


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
    from app.db.models import Org
    from app.db.repo.incidents import get_incident
    from app.domain.system_event_types import SystemEventType
    from app.services.twilio_notify import build_voice_twiml, place_call, send_sms

    inc_uuid = _uuid.UUID(incident_id)
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
            reason = "Safety manager phone number not configured. Please configure a phone number in organization settings."
            if org.sms_enabled:
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_SMS_FAILED,
                    {
                        "phone": None,
                        "reason": reason,
                    },
                )
            if org.voice_enabled:
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_CALL_FAILED,
                    {
                        "phone": None,
                        "reason": reason,
                    },
                )
            raise ValueError(reason)

        message = _compose_sms(incident)
        twiml = build_voice_twiml(_compose_voice(incident))
        errors = []
        result = {"incident_id": incident_id}

        if org.sms_enabled:
            try:
                sms_sid = send_sms(phone, message)
                result["sms_sid"] = sms_sid
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_SMS_SENT,
                    {
                        "phone": phone,
                        "sms_sid": sms_sid,
                    },
                )
            except (httpx.HTTPError, ValueError) as exc:
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_SMS_FAILED,
                    {
                        "phone": phone,
                        "reason": str(exc),
                    },
                )
                errors.append(f"SMS failed: {exc}")

        if org.voice_enabled:
            try:
                call_sid = place_call(phone, twiml)
                result["call_sid"] = call_sid
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_CALL_PLACED,
                    {
                        "phone": phone,
                        "call_sid": call_sid,
                    },
                )
            except (httpx.HTTPError, ValueError) as exc:
                _emit(
                    db,
                    inc_uuid,
                    SystemEventType.SAFETY_MANAGER_CALL_FAILED,
                    {
                        "phone": phone,
                        "reason": str(exc),
                    },
                )
                errors.append(f"Call failed: {exc}")

        if errors:
            raise RuntimeError(f"Notification failures: {'; '.join(errors)}")

        return result

    finally:
        db.close()
