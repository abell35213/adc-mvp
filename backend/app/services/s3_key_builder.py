"""Deterministic S3 key builder for court-friendly artifact paths.

Produces predictable, human-readable keys:

  org/{org_id}/incidents/{incident_id}/telematics/{artifact_type}/{artifact_id}.json
  org/{org_id}/incidents/{incident_id}/telematics/{artifact_type}/{artifact_id}.csv
  org/{org_id}/incidents/{incident_id}/telematics/{artifact_type}/{artifact_id}.pdf
  org/{org_id}/incidents/{incident_id}/dashcam/{camera_view}/{artifact_id}.mp4
  org/{org_id}/incidents/{incident_id}/exports/{export_id}/ADC_Court_Package.zip
"""

from __future__ import annotations


def telematics_key(
    org_id: str,
    incident_id: str,
    artifact_type: str,
    artifact_id: str,
    extension: str,
) -> str:
    """Build an S3 key for a telematics artifact.

    >>> telematics_key("org-1", "inc-1", "eld_log", "art-1", "json")
    'org/org-1/incidents/inc-1/telematics/eld_log/art-1.json'
    """
    ext = extension.lstrip(".")
    return (
        f"org/{org_id}/incidents/{incident_id}/telematics/"
        f"{artifact_type}/{artifact_id}.{ext}"
    )


def dashcam_key(
    org_id: str,
    incident_id: str,
    camera_view: str,
    artifact_id: str,
) -> str:
    """Build an S3 key for a dashcam artifact.

    >>> dashcam_key("org-1", "inc-1", "road_facing", "art-1")
    'org/org-1/incidents/inc-1/dashcam/road_facing/art-1.mp4'
    """
    return (
        f"org/{org_id}/incidents/{incident_id}/dashcam/"
        f"{camera_view}/{artifact_id}.mp4"
    )


def export_key(
    org_id: str,
    incident_id: str,
    export_id: str,
) -> str:
    """Build an S3 key for a court-package export.

    >>> export_key("org-1", "inc-1", "exp-1")
    'org/org-1/incidents/inc-1/exports/exp-1/ADC_Court_Package.zip'
    """
    return (
        f"org/{org_id}/incidents/{incident_id}/exports/{export_id}/ADC_Court_Package.zip"
    )
