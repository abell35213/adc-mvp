"""Builds the rendering context for telematics dataset PDF reports.

Kept separate from ``evidence_tasks`` so the Celery task module stays thin
and the context-shaping logic is independently testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


# Cap how many records we render in-line in the PDF. Telematics datasets
# can run to thousands of rows per dataset; the canonical record set is
# always available in the JSON / CSV artifacts that ship next to the PDF
# in the export package, so the PDF only needs a representative sample.
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


def _columns_from(records: list[Mapping[str, Any]]) -> list[str]:
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
    record_list = [dict(rec) for rec in records]
    record_count = len(record_list)
    truncated = record_count > max_records
    visible_records = record_list[:max_records]
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
