"""Shared export constants and enum value sets."""

EXPORT_TYPES: tuple[str, ...] = (
    "court_defense",
    "insurer_packet",
    "internal_review",
    "compliance_audit",
)

EXPORT_STATUSES: tuple[str, ...] = (
    "requested",
    "queued",
    "processing",
    "ready",
    "failed",
    "expired",
)

EXPORT_PROGRESS_STAGES: tuple[str, ...] = (
    "request_accepted",
    "gathering_incident_data",
    "assembling_documents",
    "packaging_evidence",
    "uploading_export",
    "ready_for_download",
)
