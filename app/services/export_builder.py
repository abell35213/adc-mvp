"""Export builder service."""

import logging

logger = logging.getLogger(__name__)


def build_export(incident_id: int, format: str) -> bytes:
    """Build an export package for a given incident.

    Args:
        incident_id: The ID of the incident to export.
        format: The desired export format (e.g. 'pdf', 'zip').

    Returns:
        Raw bytes of the export file.
    """
    logger.info("Building %s export for incident %d", format, incident_id)
    # Placeholder: assemble evidence and generate export
    return b""
