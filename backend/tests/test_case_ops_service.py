from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.case_ops.service import (
    build_case_snapshot,
    build_dashboard_snapshot,
    validate_case_status_transition,
)


def _artifact(status: str, artifact_type: str = "dash_cam_video_front"):
    return SimpleNamespace(status=status, artifact_type=artifact_type)


def _event(event_type: str):
    return SimpleNamespace(event_type=event_type)


def _export(status: str):
    return SimpleNamespace(status=status)


def _incident(incident_id: str, case_status: str = "in_review", created_at_utc: datetime | None = None):
    return SimpleNamespace(
        incident_id=incident_id,
        case_status=case_status,
        created_at_utc=created_at_utc or datetime.now(timezone.utc),
    )


def test_build_case_snapshot_derives_readiness_and_blockers():
    snapshot = build_case_snapshot(
        incident=_incident("inc-1", case_status="in_review"),
        artifacts=[_artifact("captured"), _artifact("pending")],
        events=[_event("incident_started")],
        exports=[_export("queued")],
    )

    assert snapshot.completeness.percent < 100
    assert snapshot.blockers.critical_count >= 1
    assert snapshot.readiness.state == "not_ready"


def test_build_dashboard_snapshot_aggregates_metrics():
    now = datetime.now(timezone.utc)
    inc_a = _incident("inc-a", created_at_utc=now - timedelta(days=2))
    inc_b = _incident("inc-b", case_status="closed", created_at_utc=now - timedelta(days=9))

    metrics = build_dashboard_snapshot(
        incidents=[inc_a, inc_b],
        artifacts_by_incident={
            "inc-a": [_artifact("captured")],
            "inc-b": [_artifact("captured")],
        },
        events_by_incident={
            "inc-a": [_event("incident_started"), _event("hash_validated")],
            "inc-b": [_event("incident_started"), _event("hash_validated"), _event("export_ready")],
        },
        exports_by_incident={
            "inc-a": [_export("ready")],
            "inc-b": [_export("ready")],
        },
    )

    assert metrics.total_open_cases >= 1
    assert metrics.closed_cases >= 1
    assert metrics.aging.over_24h >= 1


def test_validate_case_status_transition_blocks_invalid_hops():
    blocked = validate_case_status_transition(from_status="new", to_status="exported")
    allowed = validate_case_status_transition(from_status="ready_for_export", to_status="exported")

    assert blocked.allowed is False
    assert allowed.allowed is True
