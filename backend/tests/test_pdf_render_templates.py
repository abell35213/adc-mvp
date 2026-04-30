"""Unit tests for the Jinja PDF template rendering surface.

These tests exercise the HTML produced by the templates (autoescape, key
fields appearing in the document) without requiring WeasyPrint's native
runtime dependencies. The opt-in test at the bottom actually invokes
WeasyPrint and is skipped unless ``ADC_RUN_WEASYPRINT_NATIVE=1`` is set,
which CI does inside the Docker image where the native libs are present.
"""

from __future__ import annotations

import os

import pytest

from app.services.pdf_render import (
    TEMPLATE_REGISTRY,
    render_html,
    render_pdf,
)


def test_template_registry_includes_expected_documents() -> None:
    assert "cover_summary" in TEMPLATE_REGISTRY
    assert "vehicle_qr_printable" in TEMPLATE_REGISTRY
    # All telematics dataset names emitted by evidence_tasks must resolve.
    for dataset in ("eld", "gps", "safety_events", "vehicle_state"):
        assert f"{dataset}_report" in TEMPLATE_REGISTRY


def test_render_html_unknown_template_raises_value_error() -> None:
    with pytest.raises(ValueError):
        render_html("does_not_exist", {})


def test_render_html_cover_summary_includes_context_fields() -> None:
    html = render_html(
        "cover_summary",
        {
            "summary_title": "Cover Title",
            "package_root": "ADC_Export_inc-1_20260102",
            "generated_at_utc": "2026-01-02T03:04:05+00:00",
            "incident_id": "inc-1",
            "incident_status": "open",
            "incident_created_at_utc": "2026-01-01T00:00:00+00:00",
            "incident_severity": "high",
            "export_id": "exp-9",
            "export_type": "court_defense",
            "profile_id": "court_defense_v1",
            "summary_style": "litigation_full",
            "export_status": "processing",
            "artifact_count": 2,
            "timeline_event_count": 1,
            "key_events": [
                {
                    "occurred_at_utc": "2026-01-01T01:00:00+00:00",
                    "event_type": "incident_opened",
                    "actor": "driver:d-1",
                }
            ],
            "evidence_summary_counts": [{"artifact_type": "eld_log", "count": 2}],
            "missing_unavailable_warnings": [],
            "verification_instructions": ["check checksum"],
        },
    )
    assert "Cover Title" in html
    assert "ADC_Export_inc-1_20260102" in html
    assert "incident_opened" in html
    assert "check checksum" in html


def test_render_html_autoescapes_user_supplied_strings() -> None:
    html = render_html(
        "vehicle_qr_printable",
        {
            "vehicle_id": "<script>alert(1)</script>",
            "qr_token": "tok-1",
            "qr_image_data_uri": None,
        },
    )
    # Autoescape must convert the raw script tag into safe entities.
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_render_html_telematics_report_handles_empty_records() -> None:
    html = render_html(
        "telematics_report",
        {
            "dataset_name": "gps",
            "dataset_label": "GPS Trail",
            "incident_id": "inc-1",
            "record_count": 0,
            "records": [],
            "columns": [],
            "truncated": False,
            "window_start_utc": None,
            "window_end_utc": None,
            "generated_at_utc": "2026-01-02T03:04:05+00:00",
        },
    )
    assert "No records were captured" in html
    assert "GPS Trail" in html


def test_render_html_telematics_report_renders_record_rows() -> None:
    html = render_html(
        "telematics_report",
        {
            "dataset_name": "eld",
            "dataset_label": "ELD Duty Status",
            "incident_id": "inc-1",
            "record_count": 1,
            "records": [{"driver_id": "d1", "status": "on"}],
            "columns": ["driver_id", "status"],
            "truncated": False,
            "window_start_utc": "2026-01-01T00:00:00+00:00",
            "window_end_utc": "2026-01-01T01:00:00+00:00",
            "generated_at_utc": "2026-01-02T03:04:05+00:00",
        },
    )
    assert "driver_id" in html
    assert "d1" in html
    assert "ELD Duty Status" in html


def test_render_pdf_unknown_template_raises_value_error() -> None:
    with pytest.raises(ValueError):
        render_pdf("does_not_exist", {})


def test_render_pdf_uses_fake_weasyprint_and_returns_pdf_bytes() -> None:
    # Conftest's autouse fake weasyprint fixture supplies the HTML class.
    pdf = render_pdf(
        "vehicle_qr_printable",
        {"vehicle_id": "UNIT-1", "qr_token": "tok", "qr_image_data_uri": None},
    )
    assert pdf.startswith(b"%PDF")


# ── Opt-in real-WeasyPrint integration test ────────────────────────────────
# Run with: ADC_RUN_WEASYPRINT_NATIVE=1 pytest -m weasyprint_native
weasyprint_native = pytest.mark.weasyprint_native


@weasyprint_native
@pytest.mark.skipif(
    os.getenv("ADC_RUN_WEASYPRINT_NATIVE", "").lower() not in {"1", "true", "yes"},
    reason="Set ADC_RUN_WEASYPRINT_NATIVE=1 to run real WeasyPrint integration test",
)
def test_render_pdf_real_weasyprint_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    # Drop the autouse fake so the real weasyprint module is imported.
    import sys

    monkeypatch.delitem(sys.modules, "weasyprint", raising=False)
    pdf = render_pdf(
        "vehicle_qr_printable",
        {"vehicle_id": "UNIT-1", "qr_token": "tok", "qr_image_data_uri": None},
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 200
