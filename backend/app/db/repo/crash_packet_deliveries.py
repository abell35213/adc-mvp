"""Repository for crash_packet_deliveries (idempotency + SLA tracking)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import CrashPacketDelivery


def idempotency_key_for_incident(incident_id: _uuid.UUID) -> str:
    return f"crash_packet:{incident_id}"


def get_delivery_for_incident(
    db: Session, *, incident_id: _uuid.UUID
) -> CrashPacketDelivery | None:
    """Return the existing delivery row for an incident, if any."""
    return (
        db.query(CrashPacketDelivery)
        .filter(CrashPacketDelivery.incident_id == incident_id)
        .order_by(CrashPacketDelivery.created_at_utc.desc())
        .first()
    )


def create_delivery(
    db: Session,
    *,
    incident_id: _uuid.UUID,
    org_id: _uuid.UUID,
    target_sla_seconds: int,
) -> CrashPacketDelivery:
    delivery = CrashPacketDelivery(
        incident_id=incident_id,
        org_id=org_id,
        status="queued",
        target_sla_seconds=target_sla_seconds,
        idempotency_key=idempotency_key_for_incident(incident_id),
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def mark_dispatched(
    db: Session, delivery: CrashPacketDelivery, *, payload_hash: str
) -> CrashPacketDelivery:
    delivery.status = "dispatched"
    delivery.payload_hash = payload_hash
    delivery.dispatched_at_utc = datetime.now(timezone.utc)
    db.commit()
    db.refresh(delivery)
    return delivery


def mark_send_result(
    db: Session,
    delivery: CrashPacketDelivery,
    *,
    sent_to: list[dict],
    failed_to: list[dict],
    message_ids: list[str],
    error_summary: str | None = None,
) -> CrashPacketDelivery:
    delivery.sent_to = sent_to
    delivery.failed_to = failed_to
    delivery.message_ids = message_ids
    delivery.error_summary = error_summary
    if sent_to and not failed_to:
        delivery.status = "sent"
    elif sent_to and failed_to:
        delivery.status = "partial"
    else:
        delivery.status = "failed"
    delivery.delivered_at_utc = datetime.now(timezone.utc)
    db.commit()
    db.refresh(delivery)
    return delivery


def mark_overdue(
    db: Session, delivery: CrashPacketDelivery
) -> CrashPacketDelivery:
    delivery.status = "overdue"
    db.commit()
    db.refresh(delivery)
    return delivery


def find_overdue_deliveries(
    db: Session, *, now_utc: datetime
) -> list[CrashPacketDelivery]:
    """Return deliveries whose dispatched_at + SLA has elapsed but not sent."""
    candidates = (
        db.query(CrashPacketDelivery)
        .filter(
            CrashPacketDelivery.status.in_(("queued", "dispatched"))
        )
        .all()
    )
    overdue: list[CrashPacketDelivery] = []
    for d in candidates:
        if d.dispatched_at_utc is None:
            continue
        # SQLite (used in tests) returns naive datetimes for TIMESTAMP(tz=True);
        # normalize to UTC so the subtraction is well-defined on every dialect.
        dispatched = d.dispatched_at_utc
        if dispatched.tzinfo is None:
            dispatched = dispatched.replace(tzinfo=timezone.utc)
        elapsed = (now_utc - dispatched).total_seconds()
        if elapsed > d.target_sla_seconds:
            overdue.append(d)
    return overdue
