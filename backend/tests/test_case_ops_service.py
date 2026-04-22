from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.case_ops.service import (
    build_case_snapshot,
    build_dashboard_snapshot,
    validate_case_status_transition,
)
from app.case_ops.blockers import detect_blockers


def _artifact(status: str, artifact_type: str = "dash_cam_video_front"):
    return SimpleNamespace(status=status, artifact_type=artifact_type)


def _event(event_type: str):
    return SimpleNamespace(event_type=event_type)


def _export(status: str):
    return SimpleNamespace(status=status)


def _incident(
    incident_id: str,
    case_status: str = "in_review",
    created_at_utc: datetime | None = None,
):
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
    inc_b = _incident(
        "inc-b", case_status="closed", created_at_utc=now - timedelta(days=9)
    )

    metrics = build_dashboard_snapshot(
        incidents=[inc_a, inc_b],
        artifacts_by_incident={
            "inc-a": [_artifact("captured")],
            "inc-b": [_artifact("captured")],
        },
        events_by_incident={
            "inc-a": [_event("incident_started"), _event("hash_validated")],
            "inc-b": [
                _event("incident_started"),
                _event("hash_validated"),
                _event("export_ready"),
            ],
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
    allowed = validate_case_status_transition(
        from_status="ready_for_export", to_status="exported"
    )

    assert blocked.allowed is False
    assert allowed.allowed is True


def test_validate_case_status_transition_requires_privilege_for_close_and_reopen():
    close_blocked = validate_case_status_transition(
        from_status="in_review", to_status="closed"
    )
    close_allowed = validate_case_status_transition(
        from_status="in_review",
        to_status="closed",
        allow_privileged=True,
    )
    reopen_blocked = validate_case_status_transition(
        from_status="closed", to_status="in_review"
    )
    reopen_allowed = validate_case_status_transition(
        from_status="closed",
        to_status="in_review",
        allow_privileged=True,
    )

    assert close_blocked.allowed is False
    assert close_allowed.allowed is True
    assert reopen_blocked.allowed is False
    assert reopen_allowed.allowed is True


def test_detect_blockers_classifies_dashcam_and_readiness_linkage():
    summary = detect_blockers(
        artifacts=[
            _artifact("pending", "dash_cam_video_front"),
            _artifact("captured", "telematics_gps"),
        ],
        events=[_event("incident_started"), _event("capture_completed")],
        exports=[],
    )

    by_code = {blocker.code: blocker for blocker in summary.items}
    assert by_code["evidence_capture_incomplete"].missing_item.category == "dashcam"
    assert by_code["evidence_capture_incomplete"].blocks_readiness is True
    assert "evidence_capture_incomplete" in summary.readiness_blocker_codes
    assert by_code["export_not_requested"].missing_item.category == "document"
    assert by_code["export_not_requested"].blocks_readiness is False


def test_detect_blockers_classifies_driver_input_and_telematics_unavailable():
    summary = detect_blockers(
        artifacts=[
            _artifact("unavailable", "driver_statement"),
            _artifact("unavailable", "telematics_snapshot"),
            _artifact("captured", "incident_photo"),
        ],
        events=[_event("incident_started"), _event("hash_validated")],
        exports=[_export("ready")],
    )

    blocker = next(
        item for item in summary.items if item.code == "evidence_unavailable"
    )
    assert blocker.missing_item.category == "driver_input"
    assert blocker.missing_item.severity == "important"
