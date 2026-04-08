"""Private, deterministic S3 key builder for artifact storage.

All object keys are constrained to:

  orgs/{org_id}/incidents/{incident_id}/artifacts/{artifact_id}[.{extension}]

This intentionally avoids embedding sensitive details (artifact type, camera view,
or export package naming) directly in object paths.
"""

from __future__ import annotations

import re

_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_segment(name: str, value: str) -> str:
    if not value or not _SEGMENT_PATTERN.fullmatch(value):
        raise ValueError(f"{name} contains unsupported characters")
    return value


def _artifact_root(org_id: str, incident_id: str, artifact_id: str) -> str:
    org = _safe_segment("org_id", org_id)
    incident = _safe_segment("incident_id", incident_id)
    artifact = _safe_segment("artifact_id", artifact_id)
    return f"orgs/{org}/incidents/{incident}/artifacts/{artifact}"


def telematics_key(
    org_id: str,
    incident_id: str,
    artifact_type: str,
    artifact_id: str,
    extension: str,
) -> str:
    """Build an S3 key for a telematics artifact.

    Note: artifact_type is intentionally ignored for key privacy.

    >>> telematics_key("org-1", "inc-1", "eld_log", "art-1", "json")
    'orgs/org-1/incidents/inc-1/artifacts/art-1.json'
    """
    _ = artifact_type
    ext = _safe_segment("extension", extension.lstrip("."))
    return f"{_artifact_root(org_id, incident_id, artifact_id)}.{ext}"


def dashcam_key(
    org_id: str,
    incident_id: str,
    camera_view: str,
    artifact_id: str,
) -> str:
    """Build an S3 key for a dashcam artifact.

    Note: camera_view is intentionally ignored for key privacy.

    >>> dashcam_key("org-1", "inc-1", "road_facing", "art-1")
    'orgs/org-1/incidents/inc-1/artifacts/art-1.mp4'
    """
    _ = camera_view
    return f"{_artifact_root(org_id, incident_id, artifact_id)}.mp4"


def export_key(
    org_id: str,
    incident_id: str,
    export_id: str,
) -> str:
    """Build an S3 key for a court-package export.

    >>> export_key("org-1", "inc-1", "exp-1")
    'orgs/org-1/incidents/inc-1/artifacts/exp-1.zip'
    """
    return f"{_artifact_root(org_id, incident_id, export_id)}.zip"
