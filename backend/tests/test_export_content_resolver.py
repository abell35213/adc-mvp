from __future__ import annotations

from types import SimpleNamespace

from app.services.export_content_resolver import resolve_export_content


class _FakeS3:
    def __init__(self, payloads: dict[str, bytes]):
        self.payloads = payloads

    def download(self, key: str) -> bytes:
        if key not in self.payloads:
            raise FileNotFoundError(key)
        return self.payloads[key]


def test_resolver_classifies_included_excluded_unavailable_and_failed() -> None:
    artifacts = [
        SimpleNamespace(
            artifact_id="a-1",
            artifact_type="photo",
            status="captured",
            s3_key="artifacts/photo.jpg",
            sha256=None,
            byte_size=10,
        ),
        SimpleNamespace(
            artifact_id="a-2",
            artifact_type="eld_log",
            status="captured",
            s3_key="artifacts/eld.json",
            sha256=None,
            byte_size=50,
        ),
        SimpleNamespace(
            artifact_id="a-3",
            artifact_type="dash_cam_video_road",
            status="unavailable",
            s3_key=None,
            sha256=None,
            byte_size=None,
            unavailable_reason_code="retention_window_passed",
            unavailable_reason_detail=None,
        ),
        SimpleNamespace(
            artifact_id="a-4",
            artifact_type="safety_event",
            status="captured",
            s3_key="artifacts/missing.json",
            sha256=None,
            byte_size=25,
        ),
    ]

    resolved = resolve_export_content(
        incident_id="inc-1",
        export_id="exp-1",
        artifacts=artifacts,
        events=[],
        s3=_FakeS3({"artifacts/eld.json": b"{}"}),
        package_root="ADC_Export_inc-1_20260407",
        options={},
    )

    classifications = {f"{row['kind']}:{row['item']}": row["classification"] for row in resolved.file_manifest}
    assert classifications["photo:photo.jpg"] == "failed_to_retrieve"
    assert classifications["eld_log:eld.json"] == "included"
    assert classifications["dash_cam_video_road:a-3"] == "unavailable"
    assert classifications["safety_event:missing.json"] == "failed_to_retrieve"
    assert resolved.missing_items == [
        {"kind": "photo", "item": "photo.jpg"},
        {"kind": "dash_cam_video_road", "item": "a-3"},
        {"kind": "safety_event", "item": "missing.json"},
    ]
    assert any(w["reason"] == "Requested clip is outside provider retention window." for w in resolved.warnings)
