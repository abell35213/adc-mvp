"""Builds the crash-packet payload (HTML + PDF) from a CrashPacketRow."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.services.crash_packet_query import CrashPacketRow
from app.services.pdf_render import render_html, render_pdf

logger = logging.getLogger(__name__)

CRASH_BRIEF_TEMPLATE = "crash_brief"


def _row_subject(row: CrashPacketRow) -> str:
    incident = row.incident_json
    severity = incident.get("severity") or "unspecified"
    short_id = (incident.get("incident_id") or "")[:8]
    return f"[ADC] Crash brief — incident {short_id} ({severity})"


def _row_to_template_context(row: CrashPacketRow, *, subject: str) -> dict[str, Any]:
    """Map :class:`CrashPacketRow` → the names referenced by ``crash_brief.html``."""
    return {
        "subject": subject,
        "incident": row.incident_json,
        "driver": row.driver_json,
        "driver_history": row.driver_history_json,
        "vehicle": row.vehicle_json,
        "trailer": row.trailer_json,
        "maintenance": row.maintenance_json,
        "maintenance_window_days": row.maintenance_window_days,
        "eld_logs": row.eld_logs_json,
        "samsara_clip_links": row.samsara_clip_links_json,
        "related_event_count": row.related_event_count,
    }


@dataclass(frozen=True)
class CrashPacket:
    """Result of :func:`build_crash_packet` — what the email task ships."""

    subject: str
    html_body: str
    pdf_bytes: bytes
    payload_hash: str
    samsara_deep_links: list[str]


def build_crash_packet(row: CrashPacketRow) -> CrashPacket:
    """Render the HTML email body and the PDF brief from one query result.

    Also returns a stable SHA-256 hash of the ``CrashPacketRow`` so the
    ``CrashPacketDelivery`` row can prove what was sent and so duplicate
    re-dispatches can be detected.
    """
    subject = _row_subject(row)
    context = _row_to_template_context(row, subject=subject)
    html_body = render_html(CRASH_BRIEF_TEMPLATE, context)
    pdf_bytes = render_pdf(CRASH_BRIEF_TEMPLATE, context)

    deep_links = [
        clip["deep_link"]
        for clip in row.samsara_clip_links_json
        if clip.get("deep_link")
    ]

    payload_hash = hashlib.sha256(
        json.dumps(
            {
                "incident": row.incident_json,
                "driver": row.driver_json,
                "driver_history": row.driver_history_json,
                "vehicle": row.vehicle_json,
                "trailer": row.trailer_json,
                "maintenance": row.maintenance_json,
                "eld_logs": row.eld_logs_json,
                "samsara_clip_links": row.samsara_clip_links_json,
                "related_event_count": row.related_event_count,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    return CrashPacket(
        subject=subject,
        html_body=html_body,
        pdf_bytes=pdf_bytes,
        payload_hash=payload_hash,
        samsara_deep_links=deep_links,
    )
