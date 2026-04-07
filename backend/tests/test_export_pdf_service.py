from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.export_pdf_service import (
    build_export_pdf_context,
    render_cover_summary_pdf,
)


def test_build_export_pdf_context_snapshot_structure() -> None:
    incident = SimpleNamespace(
        incident_id="inc-123",
        status="open",
        created_at_utc=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        severity="high",
    )
    export = SimpleNamespace(export_id="exp-456", export_type="court_defense", status="processing")
    artifacts = [
        SimpleNamespace(artifact_type="eld_log"),
        SimpleNamespace(artifact_type="eld_log"),
        SimpleNamespace(artifact_type="gps_trail"),
    ]
    events = [
        SimpleNamespace(
            occurred_at_utc=datetime(2026, 1, 2, 4, 4, 5, tzinfo=timezone.utc),
            event_type="artifact_recorded",
            actor_type="system",
            actor_id="celery",
        ),
        SimpleNamespace(
            occurred_at_utc=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            event_type="incident_opened",
            actor_type="driver",
            actor_id="d-1",
        ),
    ]

    context = build_export_pdf_context(
        package_root="ADC_Export_inc-123_20260102",
        incident=incident,
        export=export,
        artifacts=artifacts,
        events=events,
        warnings=[{"kind": "artifact_missing_from_s3", "item": "eld/1.json", "reason": "not found"}],
        missing_items=[{"kind": "dashcam", "item": "clip.mp4"}],
        generated_at_utc="2026-01-02T03:04:06+00:00",
    )

    assert context.package_root == "ADC_Export_inc-123_20260102"
    assert context.generated_at_utc == "2026-01-02T03:04:06+00:00"
    assert context.incident_id == "inc-123"
    assert context.artifact_count == 3
    assert context.timeline_event_count == 2
    assert context.evidence_summary_counts == [
        {"artifact_type": "eld_log", "count": 2},
        {"artifact_type": "gps_trail", "count": 1},
    ]
    assert context.key_events == [
        {
            "occurred_at_utc": "2026-01-02T03:04:05+00:00",
            "event_type": "incident_opened",
            "actor": "driver:d-1",
        },
        {
            "occurred_at_utc": "2026-01-02T04:04:05+00:00",
            "event_type": "artifact_recorded",
            "actor": "system:celery",
        },
    ]
    assert context.missing_unavailable_warnings == [
        {"kind": "artifact_missing_from_s3", "item": "eld/1.json", "reason": "not found"},
        {"kind": "dashcam", "item": "clip.mp4", "reason": ""},
    ]


def test_render_cover_summary_pdf_non_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeHtml:
        def __init__(self, string: str):
            self.string = string

        def write_pdf(self) -> bytes:
            return b"%PDF-1.4\nnon-empty"

    monkeypatch.setitem(__import__("sys").modules, "weasyprint", SimpleNamespace(HTML=_FakeHtml))

    context = build_export_pdf_context(
        package_root="ADC_Export_inc-123_20260102",
        incident=SimpleNamespace(incident_id="inc-123", status="open", created_at_utc=None, severity=None),
        export=SimpleNamespace(export_id="exp-456", export_type="court_defense", status="processing"),
        artifacts=[],
        events=[],
        warnings=[],
        missing_items=[],
        generated_at_utc="2026-01-02T03:04:06+00:00",
    )

    pdf_bytes = render_cover_summary_pdf(context)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 10


def test_render_cover_summary_pdf_hard_fails_on_engine_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ExplodingHtml:
        def __init__(self, string: str):
            self.string = string

        def write_pdf(self) -> bytes:
            raise RuntimeError("engine failed")

    monkeypatch.setitem(__import__("sys").modules, "weasyprint", SimpleNamespace(HTML=_ExplodingHtml))

    context = build_export_pdf_context(
        package_root="ADC_Export_inc-123_20260102",
        incident=SimpleNamespace(incident_id="inc-123", status="open", created_at_utc=None, severity=None),
        export=SimpleNamespace(export_id="exp-456", export_type="court_defense", status="processing"),
        artifacts=[],
        events=[],
        warnings=[],
        missing_items=[],
        generated_at_utc="2026-01-02T03:04:06+00:00",
    )

    with pytest.raises(RuntimeError, match="Cover summary PDF generation failed"):
        render_cover_summary_pdf(context)
