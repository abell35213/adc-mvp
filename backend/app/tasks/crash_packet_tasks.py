"""Crash-packet workflow Celery tasks (Phase 1).

Two tasks:

* :func:`dispatch_crash_packet` — runs the canonical SQL, builds the packet,
  and emails every active recipient on the org's notification control file.
  Idempotent by ``incident_id``; safe to re-enqueue.

* :func:`crash_packet_sla_watchdog` — periodic sweep that flips dispatched
  deliveries to ``overdue`` once they exceed their SLA window.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.core.metrics import MetricNames, increment
from app.integrations.errors import IntegrationError, as_normalized_error
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    from app.db.session import SessionLocal

    return SessionLocal()


def _emit(db, *, incident_id, event_type, payload):
    from app.db.repo.events import create_event

    create_event(
        db,
        incident_id=incident_id,
        event_type=event_type,
        actor_type="system",
        actor_id="celery",
        payload=payload,
    )


@celery_app.task(
    bind=True,
    name="app.tasks.crash_packet_tasks.dispatch_crash_packet",
    acks_late=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def dispatch_crash_packet(self, incident_id: str):
    """Build and email the crash packet for ``incident_id``.

    Idempotency: the per-incident ``CrashPacketDelivery`` row uses a unique
    ``idempotency_key`` of ``crash_packet:{incident_id}``. Re-enqueues for
    the same incident reuse the row and short-circuit when already sent.
    """
    increment("crash_packet.dispatch.attempts")

    from app.db.repo.crash_packet_deliveries import (
        create_delivery,
        get_delivery_for_incident,
        mark_dispatched,
        mark_send_result,
    )
    from app.db.repo.org_notification_recipients import list_active_email_recipients
    from app.domain.system_event_types import SystemEventType
    from app.services.crash_packet_builder import build_crash_packet
    from app.services.crash_packet_query import fetch_crash_packet_row
    from app.services.email_provider import send_email

    inc_uuid = _uuid.UUID(incident_id)
    db = _get_db()
    try:
        existing = get_delivery_for_incident(db, incident_id=inc_uuid)
        if existing is not None and existing.status in {"sent", "partial"}:
            logger.info(
                "crash_packet already %s for incident %s; skipping",
                existing.status,
                incident_id,
            )
            increment("crash_packet.dispatch.skipped_duplicate")
            return {
                "incident_id": incident_id,
                "status": existing.status,
                "delivery_id": str(existing.id),
            }

        row = fetch_crash_packet_row(db, incident_id=inc_uuid)
        org_id = row.incident_json.get("org_id")
        if not org_id:
            raise ValueError(f"Incident {incident_id} has no org_id; cannot dispatch")
        org_uuid = _uuid.UUID(org_id)

        delivery = existing or create_delivery(
            db,
            incident_id=inc_uuid,
            org_id=org_uuid,
            target_sla_seconds=settings.CRASH_PACKET_SLA_SECONDS,
        )

        packet = build_crash_packet(row)
        mark_dispatched(db, delivery, payload_hash=packet.payload_hash)
        _emit(
            db,
            incident_id=inc_uuid,
            event_type=SystemEventType.CRASH_PACKET_DISPATCHED.value,
            payload={
                "delivery_id": str(delivery.id),
                "payload_hash": packet.payload_hash,
            },
        )

        recipients = list_active_email_recipients(db, org_id=org_uuid)
        if not recipients:
            logger.warning(
                "crash_packet has no active recipients for org %s (incident %s)",
                org_uuid,
                incident_id,
            )
            mark_send_result(
                db,
                delivery,
                sent_to=[],
                failed_to=[],
                message_ids=[],
                error_summary="no_active_recipients",
            )
            _emit(
                db,
                incident_id=inc_uuid,
                event_type=SystemEventType.CRASH_PACKET_FAILED.value,
                payload={
                    "delivery_id": str(delivery.id),
                    "reason": "no_active_recipients",
                },
            )
            return {
                "incident_id": incident_id,
                "status": "failed",
                "reason": "no_active_recipients",
                "delivery_id": str(delivery.id),
            }

        sent_to: list[dict] = []
        failed_to: list[dict] = []
        message_ids: list[str] = []
        for recipient in recipients:
            try:
                msg_id = send_email(
                    to=recipient.email,
                    subject=packet.subject,
                    html_body=packet.html_body,
                )
                sent_to.append(
                    {"recipient_id": str(recipient.id), "email": recipient.email}
                )
                message_ids.append(msg_id)
            except (IntegrationError, Exception) as exc:  # noqa: BLE001
                normalized = as_normalized_error(
                    exc, provider_hint="ses", category="email"
                )
                failed_to.append(
                    {
                        "recipient_id": str(recipient.id),
                        "email": recipient.email,
                        "error_code": normalized.code,
                        "reason": normalized.user_facing_message,
                    }
                )

        error_summary = None
        if failed_to and not sent_to:
            error_summary = "all_recipients_failed"
        elif failed_to:
            error_summary = "partial_failure"

        mark_send_result(
            db,
            delivery,
            sent_to=sent_to,
            failed_to=failed_to,
            message_ids=message_ids,
            error_summary=error_summary,
        )

        if sent_to and not failed_to:
            event_type = SystemEventType.CRASH_PACKET_SENT.value
        elif sent_to and failed_to:
            event_type = SystemEventType.CRASH_PACKET_SENT.value
        else:
            event_type = SystemEventType.CRASH_PACKET_FAILED.value
        _emit(
            db,
            incident_id=inc_uuid,
            event_type=event_type,
            payload={
                "delivery_id": str(delivery.id),
                "sent_count": len(sent_to),
                "failed_count": len(failed_to),
                "samsara_deep_links": packet.samsara_deep_links,
            },
        )

        return {
            "incident_id": incident_id,
            "status": delivery.status,
            "delivery_id": str(delivery.id),
            "sent_count": len(sent_to),
            "failed_count": len(failed_to),
        }
    except Exception:
        increment(MetricNames.CELERY_TASK_FAILURES)
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.crash_packet_tasks.crash_packet_sla_watchdog",
    acks_late=True,
    soft_time_limit=60,
    time_limit=90,
)
def crash_packet_sla_watchdog():
    """Flip overdue deliveries to ``overdue`` and emit metrics + audit events."""
    from app.db.repo.crash_packet_deliveries import (
        find_overdue_deliveries,
        mark_overdue,
    )
    from app.domain.system_event_types import SystemEventType

    db = _get_db()
    overdue_count = 0
    try:
        now_utc = datetime.now(timezone.utc)
        overdue = find_overdue_deliveries(db, now_utc=now_utc)
        for delivery in overdue:
            mark_overdue(db, delivery)
            increment("crash_packet.sla_breaches")
            dispatched = delivery.dispatched_at_utc
            if dispatched is not None and dispatched.tzinfo is None:
                dispatched = dispatched.replace(tzinfo=timezone.utc)
            elapsed_seconds = (
                (now_utc - dispatched).total_seconds() if dispatched else None
            )
            _emit(
                db,
                incident_id=delivery.incident_id,
                event_type=SystemEventType.CRASH_PACKET_OVERDUE.value,
                payload={
                    "delivery_id": str(delivery.id),
                    "elapsed_seconds": elapsed_seconds,
                    "target_sla_seconds": delivery.target_sla_seconds,
                },
            )
            overdue_count += 1
        return {"overdue_count": overdue_count}
    finally:
        db.close()
