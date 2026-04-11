"""Dashcam missing-reason code normalization and display helpers."""

from __future__ import annotations

from app.integrations.errors import NormalizedIntegrationError


REASON_MESSAGES: dict[str, str] = {
    "camera_not_mapped": "Camera is not mapped to the incident vehicle.",
    "retention_window_passed": "Requested clip is outside provider retention window.",
    "clip_not_available_for_window": "Clip is not available for the requested time window.",
    "provider_rate_limited": "Provider rate limit reached while retrieving dashcam footage.",
    "provider_timeout": "Provider timed out while retrieving dashcam footage.",
    "provider_unavailable": "Provider is temporarily unavailable.",
    "provider_auth_failed": "Provider authorization failed for dashcam retrieval.",
    "provider_error": "Provider reported an error while retrieving dashcam footage.",
}


def map_dashcam_missing_reason_code(
    *,
    normalized_error: NormalizedIntegrationError | None = None,
    operator_message: str | None = None,
) -> str:
    """Map integration errors/messages to canonical dashcam missing reason codes."""
    message = (operator_message or normalized_error.operator_message if normalized_error else "").lower()
    code = (normalized_error.code if normalized_error else "").upper()

    if "mapping" in message and ("missing" in message or "not found" in message):
        return "camera_not_mapped"
    if "retention" in message and ("expired" in message or "window" in message or "passed" in message):
        return "retention_window_passed"
    if code == "DASHCAM_MEDIA_NOT_AVAILABLE" or "no footage" in message or "clip not available" in message:
        return "clip_not_available_for_window"
    if code == "DASHCAM_RATE_LIMITED":
        return "provider_rate_limited"
    if code == "DASHCAM_TIMEOUT":
        return "provider_timeout"
    if code == "DASHCAM_AUTH_FAILED":
        return "provider_auth_failed"
    if code in {"DASHCAM_STREAM_UNAVAILABLE"}:
        return "provider_unavailable"
    return "provider_error"


def dashcam_reason_message(reason_code: str | None) -> str:
    """Return stable user-facing message for a reason code."""
    if not reason_code:
        return ""
    return REASON_MESSAGES.get(reason_code, reason_code)
