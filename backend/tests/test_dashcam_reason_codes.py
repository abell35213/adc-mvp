from app.integrations.errors import NormalizedIntegrationError
from app.services.dashcam_reason_codes import (
    dashcam_reason_message,
    map_dashcam_missing_reason_code,
)


def test_map_dashcam_missing_reason_code_from_error_code() -> None:
    err = NormalizedIntegrationError(
        code="DASHCAM_MEDIA_NOT_AVAILABLE",
        category="dashcam",
        provider_key="samsara",
        retryable=False,
        user_facing_message="missing",
        operator_message="no footage returned",
    )
    assert map_dashcam_missing_reason_code(normalized_error=err) == "clip_not_available_for_window"


def test_dashcam_reason_message_for_retention_code() -> None:
    assert dashcam_reason_message("retention_window_passed") == "Requested clip is outside provider retention window."
