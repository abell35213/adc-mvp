from types import SimpleNamespace

import pytest

from app.case_ops.blockers import detect_blockers


def _artifact(status: str, artifact_type: str):
    return SimpleNamespace(status=status, artifact_type=artifact_type)


@pytest.mark.parametrize(
    ("artifact_type", "expected_category"),
    [
        ("driver_statement", "driver_input"),
        ("incident_photo", "media"),
        ("telematics_snapshot", "telematics"),
        ("dash_cam_video_front", "dashcam"),
        ("police_document_pdf", "document"),
        ("unknown_custom_feed", "internal_review"),
    ],
)
def test_pending_artifact_category_classifier(artifact_type: str, expected_category: str):
    summary = detect_blockers(
        artifacts=[_artifact("pending", artifact_type)],
        events=[SimpleNamespace(event_type="incident_started"), SimpleNamespace(event_type="hash_validated")],
        exports=[SimpleNamespace(status="ready")],
    )

    pending_blocker = next(item for item in summary.items if item.code == "evidence_capture_incomplete")
    assert pending_blocker.missing_item.category == expected_category
    assert pending_blocker.missing_item.resolvableBy
    assert pending_blocker.missing_item.actionHint
