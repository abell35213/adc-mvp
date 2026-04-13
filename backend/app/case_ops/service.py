"""Facade for case ops scoring, readiness, and metrics orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from app.case_ops.blockers import detect_blockers
from app.case_ops.completeness import calculate_completeness
from app.case_ops.metrics import calculate_dashboard_metrics
from app.case_ops.models import CaseOpsSnapshot, DashboardMetrics, TransitionValidationResult
from app.case_ops.readiness import derive_readiness_state
from app.case_ops.workflow import validate_transition


def build_case_snapshot(*, incident, artifacts: list, events: list, exports: list) -> CaseOpsSnapshot:
    completeness = calculate_completeness(artifacts=artifacts, events=events, exports=exports)
    blockers = detect_blockers(artifacts=artifacts, events=events, exports=exports)
    readiness = derive_readiness_state(
        case_status=getattr(incident, "case_status", "new") or "new",
        completeness_percent=completeness.percent,
        completeness_status=completeness.status,
        blockers=blockers,
    )
    return CaseOpsSnapshot(completeness=completeness, blockers=blockers, readiness=readiness)


def build_dashboard_snapshot(
    *,
    incidents: list,
    artifacts_by_incident: dict,
    events_by_incident: dict,
    exports_by_incident: dict,
) -> DashboardMetrics:
    snapshots: list[CaseOpsSnapshot] = []
    created_at_values: list[datetime] = []
    for incident in incidents:
        incident_id = incident.incident_id
        snapshots.append(
            build_case_snapshot(
                incident=incident,
                artifacts=artifacts_by_incident.get(incident_id, []),
                events=events_by_incident.get(incident_id, []),
                exports=exports_by_incident.get(incident_id, []),
            )
        )
        created_at = getattr(incident, "created_at_utc", None)
        if created_at is not None:
            created_at_values.append(created_at)

    return calculate_dashboard_metrics(snapshots=snapshots, created_at_values=created_at_values, now=datetime.now(timezone.utc))


def validate_case_status_transition(*, from_status: str, to_status: str) -> TransitionValidationResult:
    return validate_transition(from_status=from_status, to_status=to_status)
