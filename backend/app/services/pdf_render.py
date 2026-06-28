"""PDF rendering service.

Renders evidence/export documents by composing a Jinja2 HTML template with
the supplied context and converting the result to PDF via WeasyPrint.

The public surface is intentionally narrow:

    render_pdf(template_name: str, context: dict) -> bytes

Callers stay decoupled from the templating engine and the PDF backend, and
new document types are added by:

    1. Dropping a new ``<name>.html`` Jinja template into
       ``backend/app/templates/pdf/``
    2. Registering it in ``TEMPLATE_REGISTRY`` below
    3. Building a context dict (typically via a helper in a
       ``*_pdf_context`` / service module)

Failure policy: by default any template lookup, render, or PDF backend error
is re-raised as ``RuntimeError`` so upstream evidence-integrity guarantees
are not silently weakened. Setting the env var ``PDF_RENDER_FAIL_OPEN=true``
switches the renderer to return a small placeholder PDF instead of raising,
which is intended for non-production environments only.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from app.core.config import settings

logger = logging.getLogger(__name__)


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "pdf"

# Maps logical template name (the value passed by callers) to the Jinja
# template path relative to ``TEMPLATES_DIR``. Keep entries here rather than
# letting callers reference template paths directly so we have a single,
# auditable surface of supported document types.
TEMPLATE_REGISTRY: dict[str, str] = {
    "cover_summary": "cover_summary.html",
    "vehicle_qr_printable": "vehicle_qr_printable.html",
    # Telematics dataset reports: callers pass "<dataset>_report" today
    # (eld_log_report, gps_trail_report, ...). They all share the same
    # template; the dataset name is part of the rendering context.
    "telematics_report": "telematics_report.html",
    "eld_report": "telematics_report.html",
    "gps_report": "telematics_report.html",
    "safety_events_report": "telematics_report.html",
    "vehicle_state_report": "telematics_report.html",
    # Aliases for the artifact_type-prefixed names, in case future callers
    # construct the template name from the artifact type instead of the
    # dataset name.
    "eld_log_report": "telematics_report.html",
    "gps_trail_report": "telematics_report.html",
    "safety_event_report": "telematics_report.html",
    # Crash-packet brief — sent to recipients on incident_status →
    # accident_occurred. Same Jinja template renders both the PDF and the
    # HTML email body via render_html().
    "crash_brief": "crash_brief.html",
    # Phase 3: insurance form fill — renders a structured fill of an
    # operator-uploaded template, populated from the canonical CrashPacketRow.
    "insurance_form": "insurance_form.html",
    # Court / legal-defense packet — renders the full litigation-grade
    # bundle described by the ``court_defense_v1`` packet profile (cover,
    # incident summary, evidence inventory, chain-of-custody, timeline,
    # driver statement, telemetry highlights, media inventory, integrity
    # attestation, appendix index).
    "legal_defense_packet": "legal_defense_packet.html",
}


def _build_placeholder_pdf() -> bytes:
    """Return a structurally valid minimal single-page PDF.

    Used only by the ``PDF_RENDER_FAIL_OPEN`` fail-open path. Constructed by
    hand (rather than via WeasyPrint, which is what just failed) so the
    placeholder is guaranteed to be openable in any conformant PDF viewer:
    it has a header, four objects (catalog, pages, page, trailing-content
    placeholder), a correct cross-reference table with byte offsets, a
    trailer, ``startxref`` and ``%%EOF``.
    """
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] /Resources << >> >>\nendobj\n"
        ),
    ]
    body = bytearray(header)
    offsets = [0]  # object 0 is the free entry
    for obj in objects:
        offsets.append(len(body))
        body.extend(obj)

    xref_offset = len(body)
    xref_lines = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref_lines.append(f"{off:010d} 00000 n \n")
    body.extend("".join(xref_lines).encode("ascii"))
    body.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(body)


_PLACEHOLDER_PDF = _build_placeholder_pdf()


def _fail_open() -> bool:
    return settings.PDF_RENDER_FAIL_OPEN


@lru_cache(maxsize=1)
def _jinja_env():
    """Return a lazily constructed Jinja2 environment.

    Imported lazily so importing this module does not force Jinja2 to be
    importable in environments that never render PDFs (for example, scripts
    that import unrelated services).
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "htm", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )
    return env


def _resolve_template(template_name: str) -> str:
    try:
        return TEMPLATE_REGISTRY[template_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown PDF template '{template_name}'. "
            f"Known templates: {sorted(TEMPLATE_REGISTRY)}"
        ) from exc


def render_html(template_name: str, context: Mapping[str, Any]) -> str:
    """Render the Jinja template for ``template_name`` and return the HTML.

    Exposed separately from :func:`render_pdf` so unit tests can validate
    template output without requiring WeasyPrint's native dependencies.
    """
    template_path = _resolve_template(template_name)
    template = _jinja_env().get_template(template_path)
    return template.render(**dict(context))


def render_pdf(template_name: str, context: dict) -> bytes:
    """Render a PDF from a registered template and context data.

    Returns raw PDF bytes. Raises ``ValueError`` for unknown templates and
    ``RuntimeError`` for empty/failed renders unless
    ``PDF_RENDER_FAIL_OPEN=true`` is set.
    """
    logger.info("Rendering PDF with template '%s'", template_name)
    try:
        html = render_html(template_name, context)
        # Imported lazily so test environments / non-PDF code paths do not
        # require WeasyPrint's native libs to be installed.
        from weasyprint import HTML  # type: ignore

        pdf_bytes = HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf()
    except ValueError:
        # Unknown template is a programmer error; never silently swallow.
        raise
    except Exception as exc:
        logger.exception("PDF render failed for template '%s'", template_name)
        if _fail_open():
            return _PLACEHOLDER_PDF
        raise RuntimeError(
            f"PDF render failed for template '{template_name}': {exc}"
        ) from exc

    if not pdf_bytes:
        if _fail_open():
            return _PLACEHOLDER_PDF
        raise RuntimeError(
            f"PDF render returned empty output for template '{template_name}'"
        )
    return pdf_bytes
