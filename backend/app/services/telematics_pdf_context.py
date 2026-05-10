"""Builds the rendering context for telematics dataset PDF reports.

Kept separate from ``evidence_tasks`` so the Celery task module stays thin
and the context-shaping logic is independently testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


# Cap how many records we render in-line in the PDF.
#
# Telematics datasets routinely run to several thousand rows per dataset
# (one row per GPS ping / ELD status change / safety event in the capture
# window). Rendering all of them inside a PDF table is unnecessary because:
#   - the canonical record set always ships next to the PDF in JSON + CSV
#     artifacts inside the same export ZIP, and
#   - WeasyPrint's table layout cost grows roughly linearly with row
#     count, so a 10k-row table can take seconds and produce a multi-MB
#     PDF that no human will read end-to-end.
#
# 250 rows fits comfortably in a small handful of pages while still giving
# a reviewer enough surface to spot-check the dataset. When the dataset is
# larger than this cap the template renders a "showing first N of M"
# notice pointing at the JSON/CSV artifacts.
MAX_RECORDS_IN_PDF = 250


_DATASET_LABELS: dict[str, str] = {
    "eld": "ELD Duty Status",
    "eld_log": "ELD Duty Status",
    "gps": "GPS Trail",
    "gps_trail": "GPS Trail",
    "safety_events": "Safety Events",
    "safety_event": "Safety Events",
    "vehicle_state": "Vehicle State",
}


def _dataset_label(dataset_name: str) -> str:
    return _DATASET_LABELS.get(dataset_name, dataset_name.replace("_", " ").title())


def _columns_from(records: Sequence[Mapping[str, Any]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.add(key)
                columns.append(str(key))
    return columns


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (dict, list, tuple)):
        # Stable, compact stringification for nested structures.
        return repr(value)
    return str(value)


def build_telematics_pdf_context(
    *,
    dataset_name: str,
    records: Iterable[Mapping[str, Any]],
    incident_id: str,
    window_start_utc: str | None = None,
    window_end_utc: str | None = None,
    generated_at_utc: str | None = None,
    max_records: int = MAX_RECORDS_IN_PDF,
) -> dict[str, Any]:
    """Build the context dict consumed by ``telematics_report.html``."""
    # Single streaming pass: only copy/stringify the first ``max_records``
    # records, while still counting the full input. This avoids materializing
    # the full dataset in memory inside the Celery task when the source has
    # thousands of rows but only the first N are rendered in the PDF.
    visible_records: list[dict[str, Any]] = []
    record_count = 0
    for rec in records:
        record_count += 1
        if len(visible_records) < max_records:
            visible_records.append(dict(rec))
    truncated = record_count > max_records
    columns = _columns_from(visible_records)
    # Pre-stringify cell values so the template stays free of formatting
    # logic and Jinja autoescape sees plain strings.
    rendered_records = [
        {column: _stringify(record.get(column)) for column in columns}
        for record in visible_records
    ]
    return {
        "dataset_name": dataset_name,
        "dataset_label": _dataset_label(dataset_name),
        "incident_id": incident_id,
        "record_count": record_count,
        "records": rendered_records,
        "columns": columns,
        "truncated": truncated,
        "window_start_utc": window_start_utc,
        "window_end_utc": window_end_utc,
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
    }
