"""Driver incident workflow helpers for idempotent initiation and status views."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Event, Incident
from app.db.repo.incidents import create_incident
from app.domain.system_event_types import SystemEventType


@dataclass
class IncidentInitiationResult:
    """Result of an initiation attempt."""

    incident: Incident
    protocol_already_started: bool


def get_active_incident_for_driver(
    db: Session,
    *,
    org_id: uuid.UUID,
    driver_id: uuid.UUID,
) -> Incident | None:
    """Return the latest non-closed incident for the given driver."""
    return (
        db.query(Incident)
        .filter(
            Incident.org_id == org_id,
            Incident.adc_driver_id == str(driver_id),
            Incident.status != "closed",
        )
        .order_by(desc(Incident.created_at_utc))
        .first()
    )


def get_active_incident_for_vehicle(
    db: Session,
    *,
    org_id: uuid.UUID,
    adc_vehicle_id: str,
) -> Incident | None:
    """Return the latest non-closed incident for the given vehicle."""
    return (
        db.query(Incident)
        .filter(
            Incident.org_id == org_id,
            Incident.adc_vehicle_id == adc_vehicle_id,
            Incident.status != "closed",
        )
        .order_by(desc(Incident.created_at_utc))
        .first()
    )


def _protocol_event_exists(db: Session, *, incident_id: uuid.UUID, driver_id: uuid.UUID) -> bool:
    return (
        db.query(Event.id)
        .filter(
            Event.incident_id == incident_id,
            Event.event_type == SystemEventType.INCIDENT_PROTOCOL_INITIATED.value,
            Event.actor_type == "driver_app",
            Event.actor_id == str(driver_id),
        )
        .first()
        is not None
    )




def _idempotency_key_hash(raw_key: str | None) -> str | None:
    if not raw_key:
        return None
    normalized = raw_key.strip()
    if not normalized:
        return None
    return hmac.new(settings.JWT_SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def _redacted_idempotency_payload(key_hash: str | None) -> dict[str, Any]:
    if not key_hash:
        return {}
    return {
        "idempotency_key_hash": key_hash,
        "idempotency_key_redacted": True,
    }


def initiate_driver_incident(
    db: Session,
    *,
    org_id: uuid.UUID,
    driver_id: uuid.UUID,
    adc_vehicle_id: str,
    vehicle_strategy: str,
    device_location: dict | None,
    device: dict | None,
    idempotency_key: str | None,
) -> IncidentInitiationResult:
    """Idempotently start an incident protocol for a driver.

    Reuses existing active incidents and writes protocol/lockdown events exactly once.
    """
    incident = get_active_incident_for_driver(db, org_id=org_id, driver_id=driver_id)
    if incident is None:
        incident = get_active_incident_for_vehicle(
            db,
            org_id=org_id,
            adc_vehicle_id=adc_vehicle_id,
        )
    if incident is None:
        incident = create_incident(
            db,
            status="evidence_capturing",
            adc_vehicle_id=adc_vehicle_id,
            adc_driver_id=str(driver_id),
            org_id=org_id,
        )

    key_hash = _idempotency_key_hash(idempotency_key)
    if key_hash:
        prior_events = (
            db.query(Event)
            .filter(
                Event.incident_id == incident.incident_id,
                Event.event_type == SystemEventType.INCIDENT_PROTOCOL_INITIATED.value,
                Event.actor_type == "driver_app",
                Event.actor_id == str(driver_id),
            )
            .order_by(Event.created_at_utc.desc())
            .all()
        )
        for prior in prior_events:
            payload: dict[str, Any] = cast(dict[str, Any], prior.payload or {})
            if payload.get("idempotency_key_hash") == key_hash:
                return IncidentInitiationResult(incident=incident, protocol_already_started=True)

    already_started = _protocol_event_exists(
        db,
        incident_id=cast(uuid.UUID, incident.incident_id),
        driver_id=driver_id,
    )
    if already_started:
        return IncidentInitiationResult(
            incident=incident,
            protocol_already_started=True,
        )

    event_payload = {
        "vehicle_strategy": vehicle_strategy,
        "adc_vehicle_id": adc_vehicle_id,
        "device_location": device_location,
        "device": device,
    }
    event_payload.update(_redacted_idempotency_payload(key_hash))

    protocol_event = Event(
        org_id=org_id,
        incident_id=incident.incident_id,
        event_type=SystemEventType.INCIDENT_PROTOCOL_INITIATED.value,
        actor_type="driver_app",
        actor_id=str(driver_id),
        payload=event_payload,
    )
    lockdown_event = Event(
        org_id=org_id,
        incident_id=incident.incident_id,
        event_type=SystemEventType.EVIDENCE_LOCKDOWN_STARTED.value,
        actor_type="driver_app",
        actor_id=str(driver_id),
        payload=_redacted_idempotency_payload(key_hash) or None,
    )
    db.add(protocol_event)
    db.add(lockdown_event)
    db.commit()

    return IncidentInitiationResult(
        incident=incident,
        protocol_already_started=False,
    )


def transition_incident_to_accident_occurred(
    db: Session,
    *,
    incident: Incident,
    actor_type: str = "system",
    actor_id: str = "incident_workflow",
) -> Incident:
    """Flip an incident's status to ``accident_occurred`` and dispatch the
    crash packet exactly once.

    Idempotent: re-calling for an already-flipped incident is a no-op for the
    DB, and the dispatch task itself is keyed on ``crash_packet:{incident_id}``
    so duplicate enqueues are safe. A ``CrashPacketDelivery`` row is created
    in ``queued`` status *before* the Celery enqueue so the SLA watchdog can
    detect end-to-end SLA misses (incl. broker outage / worker down / queue
    misroute) even when the dispatch task never runs. Any failure to enqueue
    is logged but not raised.
    """
    from app.domain.system_event_types import SystemEventType

    if incident.status != "accident_occurred":
        incident_row = cast(Any, incident)
        prior_status = cast(str, incident_row.status)
        incident_row.status = "accident_occurred"
        db.commit()
        db.refresh(incident)
        db.add(
            Event(
                org_id=incident.org_id,
                incident_id=incident.incident_id,
                event_type=SystemEventType.INCIDENT_STATUS_CHANGED.value,
                actor_type=actor_type,
                actor_id=actor_id,
                payload={
                    "from_status": prior_status,
                    "to_status": "accident_occurred",
                },
            )
        )
        db.commit()

    # Create the per-incident CrashPacketDelivery row in ``queued`` status
    # *before* enqueueing the Celery task. This guarantees the SLA watchdog
    # has something to find even if the task never runs (broker outage,
    # worker down, queue misroute) — the watchdog falls back to
    # ``created_at_utc`` when ``dispatched_at_utc`` is still NULL. The repo
    # row uses a unique idempotency key of ``crash_packet:{incident_id}``,
    # so re-calls of this transition (or a later dispatch task) reuse the
    # existing row rather than inserting a duplicate.
    try:
        from app.config.settings import settings as _settings
        from app.db.repo.crash_packet_deliveries import (
            create_delivery,
            get_delivery_for_incident,
        )

        if get_delivery_for_incident(db, incident_id=cast(uuid.UUID, incident.incident_id)) is None:
            create_delivery(
                db,
                incident_id=cast(uuid.UUID, incident.incident_id),
                org_id=cast(uuid.UUID, incident.org_id),
                target_sla_seconds=_settings.CRASH_PACKET_SLA_SECONDS,
            )
    except Exception:  # noqa: BLE001 - never let pre-queue bookkeeping block the flip
        import logging

        logging.getLogger(__name__).exception(
            "Failed to pre-create CrashPacketDelivery row for incident %s",
            incident.incident_id,
        )

    # Enqueue dispatch lazily so the import doesn't pull Celery into import
    # graphs that don't need it (e.g. unit tests of the transition itself).
    try:
        from app.tasks.crash_packet_tasks import dispatch_crash_packet

        dispatch_crash_packet.delay(str(incident.incident_id))
    except Exception:  # noqa: BLE001 - never let queueing block status flip
        import logging

        logging.getLogger(__name__).exception(
            "Failed to enqueue dispatch_crash_packet for incident %s",
            incident.incident_id,
        )

    return incident


def incident_status_summary(db: Session, *, incident_id: uuid.UUID) -> dict:
    """Build a complete status payload for a driver incident."""
    events = (
        db.query(Event)
        .filter(Event.incident_id == incident_id)
        .order_by(Event.occurred_at_utc.asc(), Event.created_at_utc.asc())
        .all()
    )

    evidence_event_types = {
        SystemEventType.EVIDENCE_CAPTURE_REQUESTED.value,
        SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED.value,
        SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED.value,
        SystemEventType.EVIDENCE_CAPTURE_FAILED.value,
        SystemEventType.ARTIFACT_RECORDED.value,
        SystemEventType.ARTIFACT_HASHED.value,
    }

    protocol_started_at: datetime | None = None
    evidence_requested_at: datetime | None = None
    last_evidence_update: datetime | None = None

    for event in events:
        if (
            event.event_type == SystemEventType.INCIDENT_PROTOCOL_INITIATED.value
            and protocol_started_at is None
        ):
            protocol_started_at = cast(datetime | None, event.occurred_at_utc)
        if (
            event.event_type == SystemEventType.EVIDENCE_CAPTURE_REQUESTED.value
            and evidence_requested_at is None
        ):
            evidence_requested_at = cast(datetime | None, event.occurred_at_utc)
        if event.event_type in evidence_event_types and event.occurred_at_utc is not None:
            last_evidence_update = cast(datetime | None, event.occurred_at_utc)

    return {
        "events": events,
        "protocol_started_at_utc": protocol_started_at,
        "evidence_requested_at_utc": evidence_requested_at,
        "last_evidence_update_utc": last_evidence_update,
    }
