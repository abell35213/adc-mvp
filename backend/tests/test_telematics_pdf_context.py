"""Unit tests for ``app.services.telematics_pdf_context``.

These tests pin down the context-shaping logic (column extraction, row
truncation, datetime / nested value stringification, dataset labeling)
without invoking Jinja or WeasyPrint.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.telematics_pdf_context import (
    MAX_RECORDS_IN_PDF,
    build_telematics_pdf_context,
)


def _record(**fields):
    return dict(fields)


def test_known_dataset_name_uses_friendly_label() -> None:
    ctx = build_telematics_pdf_context(
        dataset_name="gps", records=[], incident_id="inc-1"
    )
    assert ctx["dataset_label"] == "GPS Trail"
    assert ctx["dataset_name"] == "gps"


def test_unknown_dataset_name_falls_back_to_title_case() -> None:
    ctx = build_telematics_pdf_context(
        dataset_name="custom_thing", records=[], incident_id="inc-1"
    )
    assert ctx["dataset_label"] == "Custom Thing"


def test_columns_preserve_first_seen_insertion_order() -> None:
    records = [
        _record(time="t1", driver_id="d1", status="on"),
        # second record introduces a new column at the end and reuses earlier ones
        _record(driver_id="d2", time="t2", status="off", odometer=10),
    ]
    ctx = build_telematics_pdf_context(
        dataset_name="eld", records=records, incident_id="inc-1"
    )
    assert ctx["columns"] == ["time", "driver_id", "status", "odometer"]


def test_records_are_truncated_with_truncation_flag() -> None:
    records = [_record(i=i) for i in range(MAX_RECORDS_IN_PDF + 25)]
    ctx = build_telematics_pdf_context(
        dataset_name="gps", records=records, incident_id="inc-1"
    )
    assert ctx["record_count"] == MAX_RECORDS_IN_PDF + 25
    assert len(ctx["records"]) == MAX_RECORDS_IN_PDF
    assert ctx["truncated"] is True


def test_records_under_cap_are_not_marked_truncated() -> None:
    records = [_record(i=i) for i in range(5)]
    ctx = build_telematics_pdf_context(
        dataset_name="gps", records=records, incident_id="inc-1"
    )
    assert ctx["record_count"] == 5
    assert len(ctx["records"]) == 5
    assert ctx["truncated"] is False


def test_custom_max_records_cap_is_respected() -> None:
    records = [_record(i=i) for i in range(10)]
    ctx = build_telematics_pdf_context(
        dataset_name="gps",
        records=records,
        incident_id="inc-1",
        max_records=3,
    )
    assert len(ctx["records"]) == 3
    assert ctx["truncated"] is True
    assert ctx["record_count"] == 10


def test_stringify_naive_datetime_is_treated_as_utc_iso() -> None:
    naive = datetime(2026, 1, 2, 3, 4, 5)
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    ctx = build_telematics_pdf_context(
        dataset_name="gps",
        records=[_record(naive_ts=naive, aware_ts=aware)],
        incident_id="inc-1",
    )
    rendered = ctx["records"][0]
    assert rendered["naive_ts"] == "2026-01-02T03:04:05+00:00"
    assert rendered["aware_ts"] == "2026-01-02T03:04:05+00:00"


def test_stringify_none_becomes_empty_string() -> None:
    ctx = build_telematics_pdf_context(
        dataset_name="gps",
        records=[_record(field="x", missing=None)],
        incident_id="inc-1",
    )
    assert ctx["records"][0]["missing"] == ""
    assert ctx["records"][0]["field"] == "x"


def test_stringify_nested_structures_uses_repr() -> None:
    ctx = build_telematics_pdf_context(
        dataset_name="gps",
        records=[_record(meta={"a": 1}, tags=["x", "y"], pair=(1, 2))],
        incident_id="inc-1",
    )
    row = ctx["records"][0]
    assert row["meta"] == "{'a': 1}"
    assert row["tags"] == "['x', 'y']"
    assert row["pair"] == "(1, 2)"


def test_missing_columns_in_some_records_render_as_empty_cells() -> None:
    records = [
        _record(a=1, b=2),
        _record(a=3),  # no "b"
    ]
    ctx = build_telematics_pdf_context(
        dataset_name="gps", records=records, incident_id="inc-1"
    )
    assert ctx["columns"] == ["a", "b"]
    assert ctx["records"][1]["b"] == ""


def test_window_and_generated_at_are_passed_through() -> None:
    ctx = build_telematics_pdf_context(
        dataset_name="gps",
        records=[],
        incident_id="inc-1",
        window_start_utc="2026-01-01T00:00:00+00:00",
        window_end_utc="2026-01-01T01:00:00+00:00",
        generated_at_utc="2026-01-02T03:04:05+00:00",
    )
    assert ctx["window_start_utc"] == "2026-01-01T00:00:00+00:00"
    assert ctx["window_end_utc"] == "2026-01-01T01:00:00+00:00"
    assert ctx["generated_at_utc"] == "2026-01-02T03:04:05+00:00"


def test_generator_input_is_consumed_correctly() -> None:
    # Iterable (not just list) input should still work end-to-end.
    def _gen():
        for i in range(3):
            yield {"i": i}

    ctx = build_telematics_pdf_context(
        dataset_name="gps", records=_gen(), incident_id="inc-1"
    )
    assert ctx["record_count"] == 3
    assert [row["i"] for row in ctx["records"]] == ["0", "1", "2"]
