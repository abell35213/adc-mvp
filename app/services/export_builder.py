"""Export builder service."""

import logging

logger = logging.getLogger(__name__)


def build_export(incident_id: str, format: str) -> bytes:
    """Build an export package for a given incident.

    Args:
        incident_id: The UUID of the incident to export.
        format: The desired export format (e.g. 'pdf', 'zip').

    Returns:
        Raw bytes of the export file.
    """
    logger.info("Building %s export for incident %s", format, incident_id)
    # Placeholder: assemble evidence and generate export
    return b""
