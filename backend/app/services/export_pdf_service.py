"""Cover summary PDF generation for export packages."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.pdf_render import render_pdf

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
    profile_id: str
    summary_style: str
    export_status: str
    artifact_count: int
    timeline_event_count: int
    key_events: list[dict[str, str]]
    evidence_summary_counts: list[dict[str, str | int]]
    missing_unavailable_warnings: list[dict[str, str]]
    verification_instructions: list[str]


DEFAULT_VERIFICATION_INSTRUCTIONS = [
    "Run: sha256sum -c integrity/checksums.sha256 from package root.",
    "Compare package SHA-256 with the persisted export record value.",
    "Treat any checksum mismatch as potential evidence integrity failure.",
]


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
    options: dict[str, Any] | None = None,
    verification_instructions: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> ExportPdfContext:
    options = dict(options or {})
    profile_id = str(
        options.get("profile_id") or options.get("profile") or "court_defense_v1"
    )
    summary_style = (
        "claim_focused" if profile_id == "insurer_packet_v1" else "litigation_full"
    )
    counts: dict[str, int] = {}
    for artifact in artifacts:
        kind = str(getattr(artifact, "artifact_type", "unknown") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1

    evidence_summary_counts: list[dict[str, str | int]] = [
        {"artifact_type": kind, "count": count}
        for kind, count in sorted(counts.items(), key=lambda item: item[0])
    ]

    sorted_events = sorted(
        events,
        key=lambda event: (
            _iso(getattr(event, "occurred_at_utc", None)),
            str(getattr(event, "event_type", "")),
        ),
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
        profile_id=profile_id,
        summary_style=summary_style,
        export_status=str(getattr(export, "status", "unknown") or "unknown"),
        artifact_count=len(artifacts),
        timeline_event_count=len(events),
        key_events=key_events,
        evidence_summary_counts=evidence_summary_counts,
        missing_unavailable_warnings=merged_warnings,
        verification_instructions=verification_instructions
        or DEFAULT_VERIFICATION_INSTRUCTIONS,
    )


def render_cover_summary_pdf(context: ExportPdfContext) -> bytes:
    """Render the cover-summary PDF using the shared Jinja+WeasyPrint pipeline.

    Hard-fails (raises ``RuntimeError``) on any rendering error so that an
    incomplete export package is never persisted as if it were valid evidence.
    """
    summary_title = (
        "ADC Claim Packet Cover Summary"
        if context.summary_style == "claim_focused"
        else "ADC Export Cover Summary"
    )
    template_context = {**asdict(context), "summary_title": summary_title}
    try:
        pdf_bytes = render_pdf("cover_summary", template_context)
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
