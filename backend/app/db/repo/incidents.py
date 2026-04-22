"""Repository layer for incidents."""

import uuid as _uuid
from datetime import datetime, timedelta

from sqlalchemy import Text, case, cast, or_
from sqlalchemy.orm import Session

from app.db.models import Incident


def get_incident(
    db: Session,
    incident_id: _uuid.UUID,
    org_ids: list[_uuid.UUID] | None = None,
):
    query = db.query(Incident).filter(Incident.incident_id == incident_id)
    if org_ids is not None:
        query = query.filter(Incident.org_id.in_(org_ids))
    return query.first()


def list_incidents(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    org_ids: list[_uuid.UUID] | None = None,
):
    query = db.query(Incident)
    if org_ids is not None:
        query = query.filter(Incident.org_id.in_(org_ids))
    return query.offset(skip).limit(limit).all()


def create_incident(
    db: Session,
    status: str = "open",
    adc_vehicle_id: str | None = None,
    samsara_vehicle_id: str | None = None,
    adc_driver_id: str | None = None,
    severity: str | None = None,
    org_id: _uuid.UUID | None = None,
):
    incident = Incident(
        status=status,
        adc_vehicle_id=adc_vehicle_id,
        samsara_vehicle_id=samsara_vehicle_id,
        adc_driver_id=adc_driver_id,
        severity=severity,
        org_id=org_id,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def list_incident_queue(
    db: Session,
    *,
    org_ids: list[_uuid.UUID],
    case_status: str | None = None,
    owner_user_id: _uuid.UUID | None = None,
    readiness_state: str | None = None,
    created_from_utc: datetime | None = None,
    created_to_utc: datetime | None = None,
    search: str | None = None,
    sort: str = "newest",
    skip: int = 0,
    limit: int | None = 50,
) -> list[Incident]:
    """List case queue incidents with filters, pagination, and sorting."""
    if not org_ids:
        return []

    query = db.query(Incident).filter(Incident.org_id.in_(org_ids))
    if case_status:
        query = query.filter(Incident.case_status == case_status)
    if owner_user_id:
        query = query.filter(Incident.owner_user_id == owner_user_id)
    if readiness_state:
        query = query.filter(Incident.readiness_state == readiness_state)
    if created_from_utc:
        query = query.filter(Incident.created_at_utc >= created_from_utc)
    if created_to_utc:
        query = query.filter(Incident.created_at_utc <= created_to_utc)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                cast(Incident.incident_id, Text).ilike(pattern),
                Incident.adc_vehicle_id.ilike(pattern),
                Incident.samsara_vehicle_id.ilike(pattern),
                Incident.adc_driver_id.ilike(pattern),
                Incident.severity.ilike(pattern),
            )
        )

    if sort == "urgency":
        query = query.order_by(
            case(
                (Incident.case_status == "escalated", 0),
                (Incident.case_status == "awaiting_follow_up", 1),
                (Incident.case_status == "awaiting_evidence", 2),
                (Incident.case_status == "in_review", 3),
                (Incident.case_status == "new", 4),
                (Incident.case_status == "ready_for_export", 5),
                (Incident.case_status == "exported", 6),
                (Incident.case_status == "closed", 7),
                else_=8,
            ),
            Incident.last_activity_at_utc.asc().nullsfirst(),
            Incident.created_at_utc.asc(),
        )
    elif sort == "readiness":
        query = query.order_by(
            case(
                (Incident.readiness_state == "not_ready", 0),
                (Incident.readiness_state == "conditionally_ready", 1),
                (Incident.readiness_state == "ready_for_export", 2),
                (Incident.readiness_state == "exported", 3),
                (Incident.readiness_state == "closed", 4),
                else_=5,
            ),
            Incident.created_at_utc.desc(),
        )
    else:
        query = query.order_by(Incident.created_at_utc.desc())

    query = query.offset(skip)
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def count_incident_queue(
    db: Session,
    *,
    org_ids: list[_uuid.UUID],
    case_status: str | None = None,
    owner_user_id: _uuid.UUID | None = None,
    readiness_state: str | None = None,
    created_from_utc: datetime | None = None,
    created_to_utc: datetime | None = None,
    search: str | None = None,
) -> int:
    if not org_ids:
        return 0

    query = db.query(Incident).filter(Incident.org_id.in_(org_ids))
    if case_status:
        query = query.filter(Incident.case_status == case_status)
    if owner_user_id:
        query = query.filter(Incident.owner_user_id == owner_user_id)
    if readiness_state:
        query = query.filter(Incident.readiness_state == readiness_state)
    if created_from_utc:
        query = query.filter(Incident.created_at_utc >= created_from_utc)
    if created_to_utc:
        query = query.filter(Incident.created_at_utc <= created_to_utc)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                cast(Incident.incident_id, Text).ilike(pattern),
                Incident.adc_vehicle_id.ilike(pattern),
                Incident.samsara_vehicle_id.ilike(pattern),
                Incident.adc_driver_id.ilike(pattern),
                Incident.severity.ilike(pattern),
            )
        )
    return query.count()


def count_incident_alerts(
    db: Session,
    *,
    org_ids: list[_uuid.UUID],
    now_utc: datetime,
) -> dict[str, int]:
    """Count incidents requiring queue alerts."""
    if not org_ids:
        return {
            "stalled": 0,
            "unassigned": 0,
            "blocked": 0,
            "export_aging": 0,
        }

    base = db.query(Incident).filter(
        Incident.org_id.in_(org_ids), Incident.case_status != "closed"
    )
    stalled_cutoff = now_utc - timedelta(hours=72)
    export_aging_cutoff = now_utc - timedelta(hours=48)

    return {
        "stalled": base.filter(
            Incident.last_activity_at_utc.is_not(None),
            Incident.last_activity_at_utc <= stalled_cutoff,
        ).count(),
        "unassigned": base.filter(Incident.owner_user_id.is_(None)).count(),
        "blocked": base.filter(Incident.readiness_state == "not_ready").count(),
        "export_aging": db.query(Incident)
        .filter(
            Incident.org_id.in_(org_ids),
            Incident.case_status == "ready_for_export",
            Incident.ready_for_export_at_utc.is_not(None),
            Incident.ready_for_export_at_utc <= export_aging_cutoff,
        )
        .count(),
    }
