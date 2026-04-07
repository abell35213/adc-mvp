"""Cover summary PDF generation for export packages."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportPdfContext:
    """Template context for the cover summary PDF (Section 11)."""

    package_root: str
    generated_at_utc: str
    incident_id: str
    incident_status: str
    incident_created_at_utc: str
    incident_severity: str
    export_id: str
    export_type: str
    export_status: str
    artifact_count: int
    timeline_event_count: int
    key_events: list[dict[str, str]]
    evidence_summary_counts: list[dict[str, int]]
    missing_unavailable_warnings: list[dict[str, str]]
    verification_instructions: list[str]


DEFAULT_VERIFICATION_INSTRUCTIONS = [
    "Run: sha256sum -c integrity/checksums.sha256 from package root.",
    "Compare package SHA-256 with the persisted export record value.",
    "Treat any checksum mismatch as potential evidence integrity failure.",
]


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <style>
    @page {{ size: A4; margin: 1.6cm; }}
    body {{ font-family: Arial, sans-serif; color: #111; font-size: 11pt; }}
    h1, h2 {{ margin: 0 0 8px 0; }}
    h1 {{ font-size: 18pt; }}
    h2 {{ font-size: 13pt; margin-top: 14px; }}
    .muted {{ color: #555; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; vertical-align: top; }}
    ul {{ margin-top: 4px; }}
    .warning {{ color: #8a2c2c; }}
  </style>
</head>
<body>
  <h1>ADC Export Cover Summary</h1>
  <p class=\"muted\">Package: {package_root}</p>
  <p class=\"muted\">Generated: {generated_at_utc}</p>

  <h2>Incident Summary Facts</h2>
  <table>
    <tr><th>Incident ID</th><td>{incident_id}</td></tr>
    <tr><th>Incident Status</th><td>{incident_status}</td></tr>
    <tr><th>Incident Created</th><td>{incident_created_at_utc}</td></tr>
    <tr><th>Severity</th><td>{incident_severity}</td></tr>
    <tr><th>Export ID</th><td>{export_id}</td></tr>
    <tr><th>Export Type</th><td>{export_type}</td></tr>
    <tr><th>Export Status</th><td>{export_status}</td></tr>
    <tr><th>Artifact Count</th><td>{artifact_count}</td></tr>
    <tr><th>Timeline Event Count</th><td>{timeline_event_count}</td></tr>
  </table>

  <h2>Key Events</h2>
  <table>
    <tr><th>Occurred UTC</th><th>Event Type</th><th>Actor</th></tr>
    {key_events_rows}
  </table>

  <h2>Evidence Summary Counts</h2>
  <table>
    <tr><th>Artifact Type</th><th>Count</th></tr>
    {evidence_summary_rows}
  </table>

  <h2>Missing/Unavailable Warnings</h2>
  <ul>
    {warning_rows}
  </ul>

  <h2>Verification Instructions</h2>
  <ol>
    {verification_rows}
  </ol>
</body>
</html>
"""


def _iso(dt: Any) -> str:
    if not dt:
        return "unknown"
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(dt)


def build_export_pdf_context(
    *,
    package_root: str,
    incident: Any,
    export: Any,
    artifacts: list[Any],
    events: list[Any],
    warnings: list[dict[str, str]],
    missing_items: list[dict[str, str]],
    verification_instructions: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> ExportPdfContext:
    counts: dict[str, int] = {}
    for artifact in artifacts:
        kind = str(getattr(artifact, "artifact_type", "unknown") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1

    evidence_summary_counts = [
        {"artifact_type": kind, "count": count}
        for kind, count in sorted(counts.items(), key=lambda item: item[0])
    ]

    sorted_events = sorted(
        events,
        key=lambda event: (_iso(getattr(event, "occurred_at_utc", None)), str(getattr(event, "event_type", ""))),
    )
    key_events = [
        {
            "occurred_at_utc": _iso(getattr(event, "occurred_at_utc", None)),
            "event_type": str(getattr(event, "event_type", "unknown") or "unknown"),
            "actor": f"{getattr(event, 'actor_type', 'unknown')}:{getattr(event, 'actor_id', 'unknown')}",
        }
        for event in sorted_events[:10]
    ]

    merged_warnings = [
        {
            "kind": str(item.get("kind") or "warning"),
            "item": str(item.get("item") or "unknown"),
            "reason": str(item.get("reason") or ""),
        }
        for item in [*warnings, *missing_items]
    ]

    return ExportPdfContext(
        package_root=package_root,
        generated_at_utc=generated_at_utc or datetime.now(timezone.utc).isoformat(),
        incident_id=str(getattr(incident, "incident_id", "unknown")),
        incident_status=str(getattr(incident, "status", "unknown") or "unknown"),
        incident_created_at_utc=_iso(getattr(incident, "created_at_utc", None)),
        incident_severity=str(getattr(incident, "severity", "unknown") or "unknown"),
        export_id=str(getattr(export, "export_id", "unknown")),
        export_type=str(getattr(export, "export_type", "unknown") or "unknown"),
        export_status=str(getattr(export, "status", "unknown") or "unknown"),
        artifact_count=len(artifacts),
        timeline_event_count=len(events),
        key_events=key_events,
        evidence_summary_counts=evidence_summary_counts,
        missing_unavailable_warnings=merged_warnings,
        verification_instructions=verification_instructions or DEFAULT_VERIFICATION_INSTRUCTIONS,
    )


def render_cover_summary_pdf(context: ExportPdfContext) -> bytes:
    key_events_rows = "".join(
        f"<tr><td>{escape(event['occurred_at_utc'])}</td><td>{escape(event['event_type'])}</td><td>{escape(event['actor'])}</td></tr>"
        for event in context.key_events
    ) or "<tr><td colspan='3'>No events recorded.</td></tr>"

    evidence_summary_rows = "".join(
        f"<tr><td>{escape(row['artifact_type'])}</td><td>{row['count']}</td></tr>"
        for row in context.evidence_summary_counts
    ) or "<tr><td colspan='2'>No artifacts listed.</td></tr>"

    warning_rows = "".join(
        f"<li class='warning'>{escape(row['kind'])} / {escape(row['item'])} {escape(row['reason'])}</li>"
        for row in context.missing_unavailable_warnings
    ) or "<li>No warnings.</li>"

    verification_rows = "".join(
        f"<li>{escape(item)}</li>" for item in context.verification_instructions
    )

    html = HTML_TEMPLATE.format(
        **{k: escape(str(v)) for k, v in asdict(context).items() if not isinstance(v, list)},
        key_events_rows=key_events_rows,
        evidence_summary_rows=evidence_summary_rows,
        warning_rows=warning_rows,
        verification_rows=verification_rows,
    )

    try:
        from weasyprint import HTML  # type: ignore

        pdf_bytes = HTML(string=html).write_pdf()
    except Exception as exc:  # hard-fail policy for MVP defensibility
        logger.exception(
            "Failed to generate cover summary PDF for export_id=%s incident_id=%s",
            context.export_id,
            context.incident_id,
        )
        raise RuntimeError(
            f"Cover summary PDF generation failed for export {context.export_id}: {exc}"
        ) from exc

    if not pdf_bytes:
        raise RuntimeError(
            f"Cover summary PDF generation returned empty output for export {context.export_id}"
        )
    return pdf_bytes
