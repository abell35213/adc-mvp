"""Dashboard counters and aging metrics for case operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.case_ops.blockers import detect_blockers
from app.case_ops.completeness import calculate_completeness
from app.case_ops.models import AgingMetrics, DashboardMetrics, CaseOpsSnapshot
from app.case_ops.readiness import derive_readiness_state
from app.db.models import Artifact, Event, Export, Incident
from app.db.repo.case_tasks import count_overdue_tasks
from app.db.repo.incidents import count_incident_alerts, count_incident_queue, list_incident_queue


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = max(0, min(len(sorted_values) - 1, round((percentile / 100) * (len(sorted_values) - 1))))
    return sorted_values[rank]


def calculate_dashboard_metrics(*, snapshots: list[CaseOpsSnapshot], created_at_values: list[datetime], now: datetime | None = None) -> DashboardMetrics:
    now_utc = now or datetime.now(timezone.utc)
    normalized_created_at_values = [
        created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
        for created_at in created_at_values
    ]
    ages_days = [
        max(0.0, (now_utc - created_at).total_seconds() / 86400.0)
        for created_at in normalized_created_at_values
    ]

    not_ready_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "not_ready")
    conditionally_ready_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "conditionally_ready")
    ready_for_export_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "ready_for_export")
    exported_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "exported")
    closed_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "closed")

    return DashboardMetrics(
        total_open_cases=sum(1 for snapshot in snapshots if snapshot.readiness.state != "closed"),
        not_ready_cases=not_ready_cases,
        conditionally_ready_cases=conditionally_ready_cases,
        ready_for_export_cases=ready_for_export_cases,
        exported_cases=exported_cases,
        closed_cases=closed_cases,
        cases_with_critical_blockers=sum(1 for snapshot in snapshots if snapshot.blockers.critical_count > 0),
        cases_with_important_blockers=sum(1 for snapshot in snapshots if snapshot.blockers.important_count > 0),
        aging=AgingMetrics(
            average_age_days=(sum(ages_days) / len(ages_days)) if ages_days else 0.0,
            p95_age_days=_percentile(ages_days, 95),
            over_24h=sum(1 for age in ages_days if age >= 1),
            over_72h=sum(1 for age in ages_days if age >= 3),
            over_7d=sum(1 for age in ages_days if age >= 7),
        ),
    )


def query_incident_queue(
    db: Session,
    *,
    org_ids: list[uuid.UUID],
    case_status: str | None = None,
    owner_user_id: uuid.UUID | None = None,
    readiness_state: str | None = None,
    created_from_utc: datetime | None = None,
    created_to_utc: datetime | None = None,
    blockers: Literal["any", "critical", "important", "none"] | None = None,
    search: str | None = None,
    sort: Literal["urgency", "readiness", "newest"] = "newest",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    skip = max(page - 1, 0) * page_size
    apply_blocker_filter = blockers is not None
    incidents = list_incident_queue(
        db,
        org_ids=org_ids,
        case_status=case_status,
        owner_user_id=owner_user_id,
        readiness_state=readiness_state,
        created_from_utc=created_from_utc,
        created_to_utc=created_to_utc,
        search=search,
        sort=sort,
        skip=0 if apply_blocker_filter else skip,
        limit=None if apply_blocker_filter else page_size,
    )
    if not incidents:
        total = 0 if apply_blocker_filter else count_incident_queue(
            db,
            org_ids=org_ids,
            case_status=case_status,
            owner_user_id=owner_user_id,
            readiness_state=readiness_state,
            created_from_utc=created_from_utc,
            created_to_utc=created_to_utc,
            search=search,
        )
        return {"items": [], "total": total, "page": page, "page_size": page_size}

    incident_ids = [incident.incident_id for incident in incidents]
    artifacts_by_incident: dict[uuid.UUID, list[Artifact]] = {}
    events_by_incident: dict[uuid.UUID, list[Event]] = {}
    exports_by_incident: dict[uuid.UUID, list[Export]] = {}
    for artifact in db.query(Artifact).filter(Artifact.incident_id.in_(incident_ids)).all():
        artifacts_by_incident.setdefault(artifact.incident_id, []).append(artifact)
    for event in db.query(Event).filter(Event.incident_id.in_(incident_ids)).all():
        events_by_incident.setdefault(event.incident_id, []).append(event)
    for export in db.query(Export).filter(Export.incident_id.in_(incident_ids)).all():
        exports_by_incident.setdefault(export.incident_id, []).append(export)

    queue_items: list[dict] = []
    for incident in incidents:
        snapshot = _build_snapshot(
            incident=incident,
            artifacts=artifacts_by_incident.get(incident.incident_id, []),
            events=events_by_incident.get(incident.incident_id, []),
            exports=exports_by_incident.get(incident.incident_id, []),
        )
        queue_item = _build_queue_item(incident=incident, snapshot=snapshot)
        if _matches_blocker_filter(snapshot=snapshot, blockers=blockers):
            queue_items.append(queue_item)

    if apply_blocker_filter:
        total = len(queue_items)
        page_items = queue_items[skip : skip + page_size]
    else:
        total = count_incident_queue(
            db,
            org_ids=org_ids,
            case_status=case_status,
            owner_user_id=owner_user_id,
            readiness_state=readiness_state,
            created_from_utc=created_from_utc,
            created_to_utc=created_to_utc,
            search=search,
        )
        page_items = queue_items

    return {"items": page_items, "total": total, "page": page, "page_size": page_size}


def query_summary_metrics(
    db: Session,
    *,
    org_ids: list[uuid.UUID],
    now_utc: datetime | None = None,
) -> dict:
    now = now_utc or datetime.now(timezone.utc)
    open_incident_count = count_incident_queue(
        db,
        org_ids=org_ids,
    )
    alert_counts = count_incident_alerts(db, org_ids=org_ids, now_utc=now)
    overdue_tasks = count_overdue_tasks(db, org_ids=org_ids, now_utc=now)
    return {
        "open_incidents": open_incident_count,
        "unassigned_incidents": alert_counts["unassigned"],
        "blocked_incidents": alert_counts["blocked"],
        "export_aging_incidents": alert_counts["export_aging"],
        "stalled_incidents": alert_counts["stalled"],
        "overdue_tasks": overdue_tasks,
    }


def query_case_alerts(
    db: Session,
    *,
    org_ids: list[uuid.UUID],
    now_utc: datetime | None = None,
) -> dict:
    now = now_utc or datetime.now(timezone.utc)
    alert_counts = count_incident_alerts(db, org_ids=org_ids, now_utc=now)
    return {
        "stalled": alert_counts["stalled"],
        "unassigned": alert_counts["unassigned"],
        "blocked": alert_counts["blocked"],
        "overdue": count_overdue_tasks(db, org_ids=org_ids, now_utc=now),
        "export_aging": alert_counts["export_aging"],
    }


def _matches_blocker_filter(
    *,
    snapshot: CaseOpsSnapshot,
    blockers: Literal["any", "critical", "important", "none"] | None,
) -> bool:
    if blockers is None:
        return True
    if blockers == "any":
        return snapshot.blockers.total > 0
    if blockers == "critical":
        return snapshot.blockers.critical_count > 0
    if blockers == "important":
        return snapshot.blockers.important_count > 0
    if blockers == "none":
        return snapshot.blockers.total == 0
    return True


def _build_queue_item(*, incident: Incident, snapshot: CaseOpsSnapshot) -> dict:
    return {
        "incident_id": incident.incident_id,
        "case_status": incident.case_status,
        "owner_user_id": incident.owner_user_id,
        "readiness_state": snapshot.readiness.state,
        "created_at_utc": incident.created_at_utc,
        "last_activity_at_utc": incident.last_activity_at_utc,
        "severity": incident.severity,
        "adc_vehicle_id": incident.adc_vehicle_id,
        "adc_driver_id": incident.adc_driver_id,
        "completeness_percent": snapshot.completeness.percent,
        "blockers": {
            "total": snapshot.blockers.total,
            "critical": snapshot.blockers.critical_count,
            "important": snapshot.blockers.important_count,
            "optional": snapshot.blockers.optional_count,
        },
    }


def _build_snapshot(*, incident, artifacts: list, events: list, exports: list) -> CaseOpsSnapshot:
    completeness = calculate_completeness(artifacts=artifacts, events=events, exports=exports)
    blockers = detect_blockers(artifacts=artifacts, events=events, exports=exports)
    readiness = derive_readiness_state(
        case_status=getattr(incident, "case_status", "new") or "new",
        completeness_percent=completeness.percent,
        completeness_status=completeness.status,
        blockers=blockers,
    )
    return CaseOpsSnapshot(completeness=completeness, blockers=blockers, readiness=readiness)
