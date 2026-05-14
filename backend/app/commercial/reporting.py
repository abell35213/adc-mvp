"""Reporting feature gates and aggregate query helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.case_ops.completeness import calculate_completeness
from app.case_ops.metrics import query_summary_metrics
from app.db.models import Artifact, Event, Export, Incident

REPORT_ADOPTION_FEATURE = "reporting.adoption"
REPORT_INCIDENT_OPERATIONS_FEATURE = "reporting.incident_operations"
REPORT_EXPORT_TURNAROUND_FEATURE = "reporting.export_turnaround"
REPORT_EVIDENCE_COMPLETENESS_FEATURE = "reporting.evidence_completeness"

PREMIUM_REPORTING_FEATURES: tuple[str, ...] = (
    REPORT_INCIDENT_OPERATIONS_FEATURE,
    REPORT_EXPORT_TURNAROUND_FEATURE,
)
FUTURE_REPORTING_FEATURES: tuple[str, ...] = (REPORT_EVIDENCE_COMPLETENESS_FEATURE,)

REPORTING_FEATURES: tuple[str, ...] = (
    "reporting.dashboard",
    "reporting.audit_trail",
    "reporting.export_history",
    REPORT_ADOPTION_FEATURE,
)


def _normalize_to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def query_adoption_report(db: Session, *, org_ids: list[uuid.UUID]) -> dict[str, Any]:
    if not org_ids:
        return {
            "total_incidents": 0,
            "reviewed_incidents": 0,
            "assigned_incidents": 0,
            "ready_for_export_incidents": 0,
            "exported_incidents": 0,
            "review_rate_percent": 0.0,
            "assignment_rate_percent": 0.0,
            "export_readiness_rate_percent": 0.0,
            "export_completion_rate_percent": 0.0,
            "adoption_score_percent": 0.0,
        }

    base_query = db.query(Incident).filter(
        Incident.org_id.in_(org_ids),
        Incident.is_test_incident.is_(False),
    )
    total_incidents = base_query.count()
    reviewed_incidents = base_query.filter(Incident.first_reviewed_at_utc.is_not(None)).count()
    assigned_incidents = base_query.filter(Incident.owner_user_id.is_not(None)).count()
    ready_for_export_incidents = base_query.filter(
        Incident.ready_for_export_at_utc.is_not(None)
    ).count()
    exported_incidents = (
        db.query(func.count(func.distinct(Export.incident_id)))
        .filter(
            Export.org_id.in_(org_ids),
            Export.status == "ready",
        )
        .scalar()
        or 0
    )

    review_rate = _percent(reviewed_incidents, total_incidents)
    assignment_rate = _percent(assigned_incidents, total_incidents)
    readiness_rate = _percent(ready_for_export_incidents, total_incidents)
    export_completion_rate = _percent(exported_incidents, total_incidents)
    adoption_score = round((review_rate + assignment_rate + readiness_rate) / 3.0, 2)
    return {
        "total_incidents": total_incidents,
        "reviewed_incidents": reviewed_incidents,
        "assigned_incidents": assigned_incidents,
        "ready_for_export_incidents": ready_for_export_incidents,
        "exported_incidents": int(exported_incidents),
        "review_rate_percent": review_rate,
        "assignment_rate_percent": assignment_rate,
        "export_readiness_rate_percent": readiness_rate,
        "export_completion_rate_percent": export_completion_rate,
        "adoption_score_percent": adoption_score,
    }


def query_incident_operations_report(
    db: Session, *, org_ids: list[uuid.UUID]
) -> dict[str, Any]:
    summary = query_summary_metrics(db, org_ids=org_ids)
    if not org_ids:
        return {
            **summary,
            "case_status_counts": {},
            "avg_time_to_first_review_hours": 0.0,
            "incidents_reviewed": 0,
        }

    case_status_rows = (
        db.query(Incident.case_status, func.count(Incident.incident_id))
        .filter(
            Incident.org_id.in_(org_ids),
            Incident.is_test_incident.is_(False),
        )
        .group_by(Incident.case_status)
        .all()
    )
    case_status_counts = {str(status): int(count) for status, count in case_status_rows}

    review_seconds_expr = (
        func.extract("epoch", Incident.first_reviewed_at_utc)
        - func.extract("epoch", Incident.created_at_utc)
    )
    avg_review_seconds = (
        db.query(func.avg(review_seconds_expr))
        .filter(
            Incident.org_id.in_(org_ids),
            Incident.is_test_incident.is_(False),
            Incident.first_reviewed_at_utc.is_not(None),
        )
        .scalar()
    )
    incidents_reviewed = (
        db.query(func.count(Incident.incident_id))
        .filter(
            Incident.org_id.in_(org_ids),
            Incident.is_test_incident.is_(False),
            Incident.first_reviewed_at_utc.is_not(None),
        )
        .scalar()
        or 0
    )

    return {
        **summary,
        "case_status_counts": case_status_counts,
        "avg_time_to_first_review_hours": round(float(avg_review_seconds or 0.0) / 3600.0, 2),
        "incidents_reviewed": int(incidents_reviewed),
    }


def query_export_turnaround_report(
    db: Session, *, org_ids: list[uuid.UUID]
) -> dict[str, Any]:
    if not org_ids:
        return {
            "total_exports": 0,
            "completed_exports": 0,
            "failed_exports": 0,
            "in_flight_exports": 0,
            "avg_turnaround_hours": 0.0,
            "p95_turnaround_hours": 0.0,
            "within_24h_rate_percent": 0.0,
        }

    exports = (
        db.query(Export)
        .filter(Export.org_id.in_(org_ids))
        .order_by(Export.created_at_utc.desc())
        .all()
    )
    total_exports = len(exports)
    completed_exports = 0
    failed_exports = 0
    in_flight_exports = 0
    turnaround_hours: list[float] = []
    within_24h = 0
    for export in exports:
        if export.status == "failed":
            failed_exports += 1
        elif export.status == "ready":
            completed_exports += 1
        else:
            in_flight_exports += 1

        start = _normalize_to_utc(cast(Any, export.requested_at_utc))
        end = _normalize_to_utc(cast(Any, export.completed_at_utc))
        if start is None or end is None or end < start:
            continue
        hours = (end - start).total_seconds() / 3600.0
        turnaround_hours.append(hours)
        if hours <= 24.0:
            within_24h += 1

    sorted_turnaround = sorted(turnaround_hours)
    p95_turnaround = (
        sorted_turnaround[max(0, round(0.95 * (len(sorted_turnaround) - 1)))]
        if sorted_turnaround
        else 0.0
    )
    avg_turnaround = (
        sum(sorted_turnaround) / len(sorted_turnaround) if sorted_turnaround else 0.0
    )

    return {
        "total_exports": total_exports,
        "completed_exports": completed_exports,
        "failed_exports": failed_exports,
        "in_flight_exports": in_flight_exports,
        "avg_turnaround_hours": round(avg_turnaround, 2),
        "p95_turnaround_hours": round(float(p95_turnaround), 2),
        "within_24h_rate_percent": _percent(within_24h, len(sorted_turnaround)),
    }


def query_evidence_completeness_report(
    db: Session, *, org_ids: list[uuid.UUID]
) -> dict[str, Any]:
    if not org_ids:
        return {
            "total_incidents": 0,
            "avg_completeness_percent": 0.0,
            "readiness_breakdown": {"not_ready": 0, "conditionally_ready": 0, "ready": 0},
            "artifact_status_counts": {"captured": 0, "pending": 0, "unavailable": 0},
        }

    incidents = (
        db.query(Incident)
        .filter(Incident.org_id.in_(org_ids), Incident.is_test_incident.is_(False))
        .all()
    )
    if not incidents:
        return {
            "total_incidents": 0,
            "avg_completeness_percent": 0.0,
            "readiness_breakdown": {"not_ready": 0, "conditionally_ready": 0, "ready": 0},
            "artifact_status_counts": {"captured": 0, "pending": 0, "unavailable": 0},
        }

    incident_ids = [incident.incident_id for incident in incidents]
    artifacts = db.query(Artifact).filter(Artifact.incident_id.in_(incident_ids)).all()
    events = db.query(Event).filter(Event.incident_id.in_(incident_ids)).all()
    exports = db.query(Export).filter(Export.incident_id.in_(incident_ids)).all()

    artifacts_by_incident: dict[uuid.UUID, list[Artifact]] = {}
    events_by_incident: dict[uuid.UUID, list[Event]] = {}
    exports_by_incident: dict[uuid.UUID, list[Export]] = {}
    artifact_status_counts = {"captured": 0, "pending": 0, "unavailable": 0}
    for artifact in artifacts:
        artifacts_by_incident.setdefault(cast(uuid.UUID, artifact.incident_id), []).append(artifact)
        if artifact.status in artifact_status_counts:
            artifact_status_counts[str(artifact.status)] += 1
    for event in events:
        events_by_incident.setdefault(cast(uuid.UUID, event.incident_id), []).append(event)
    for export in exports:
        exports_by_incident.setdefault(cast(uuid.UUID, export.incident_id), []).append(export)

    completeness_total = 0
    readiness_breakdown = {"not_ready": 0, "conditionally_ready": 0, "ready": 0}
    for incident in incidents:
        completeness = calculate_completeness(
            artifacts=artifacts_by_incident.get(cast(uuid.UUID, incident.incident_id), []),
            events=events_by_incident.get(cast(uuid.UUID, incident.incident_id), []),
            exports=exports_by_incident.get(cast(uuid.UUID, incident.incident_id), []),
        )
        completeness_total += completeness.percent
        if completeness.percent >= 90:
            readiness_breakdown["ready"] += 1
        elif completeness.percent >= 60:
            readiness_breakdown["conditionally_ready"] += 1
        else:
            readiness_breakdown["not_ready"] += 1

    return {
        "total_incidents": len(incidents),
        "avg_completeness_percent": round(completeness_total / len(incidents), 2),
        "readiness_breakdown": readiness_breakdown,
        "artifact_status_counts": artifact_status_counts,
    }
