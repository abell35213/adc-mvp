"""PDF rendering service."""

import logging

logger = logging.getLogger(__name__)


def render_pdf(template_name: str, context: dict) -> bytes:
    """Render a PDF from a template and context data.

    Returns raw PDF bytes.
    """
    logger.info("Rendering PDF with template '%s'", template_name)
    # Placeholder: integrate a PDF library (e.g. WeasyPrint, ReportLab)
    return b"%PDF-1.4 placeholder"
