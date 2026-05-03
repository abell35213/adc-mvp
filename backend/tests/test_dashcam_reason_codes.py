from app.integrations.errors import NormalizedIntegrationError
from app.services.dashcam_reason_codes import (
    REASON_MESSAGES,
    dashcam_reason_message,
    map_dashcam_missing_reason_code,
)


def _make_error(code: str = "", operator_message: str = "") -> NormalizedIntegrationError:
    return NormalizedIntegrationError(
        code=code,
        category="dashcam",
        provider_key="samsara",
        retryable=False,
        user_facing_message="",
        operator_message=operator_message,
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


# --- map_dashcam_missing_reason_code: operator_message based branches ---


def test_camera_not_mapped_from_operator_message_missing() -> None:
    err = _make_error()
    assert (
        map_dashcam_missing_reason_code(
            normalized_error=err, operator_message="vehicle mapping is missing"
        )
        == "camera_not_mapped"
    )


def test_camera_not_mapped_from_operator_message_not_found() -> None:
    err = _make_error()
    assert (
        map_dashcam_missing_reason_code(
            normalized_error=err, operator_message="camera mapping not found"
        )
        == "camera_not_mapped"
    )


def test_retention_window_passed_from_operator_message_expired() -> None:
    err = _make_error(operator_message="Retention period expired")
    assert (
        map_dashcam_missing_reason_code(normalized_error=err)
        == "retention_window_passed"
    )


def test_retention_window_passed_from_operator_message_window() -> None:
    err = _make_error(operator_message="retention window exceeded")
    assert (
        map_dashcam_missing_reason_code(normalized_error=err)
        == "retention_window_passed"
    )


def test_retention_window_passed_from_operator_message_passed() -> None:
    err = _make_error(operator_message="Retention has passed")
    assert (
        map_dashcam_missing_reason_code(normalized_error=err)
        == "retention_window_passed"
    )


def test_clip_not_available_from_operator_message_no_footage() -> None:
    err = _make_error(code="OTHER_CODE", operator_message="no footage available")
    assert (
        map_dashcam_missing_reason_code(normalized_error=err)
        == "clip_not_available_for_window"
    )


def test_clip_not_available_from_operator_message_clip_not_available() -> None:
    err = _make_error(code="OTHER", operator_message="Clip not available for window")
    assert (
        map_dashcam_missing_reason_code(normalized_error=err)
        == "clip_not_available_for_window"
    )


# --- map_dashcam_missing_reason_code: code based branches ---


def test_rate_limited_code() -> None:
    err = _make_error(code="DASHCAM_RATE_LIMITED")
    assert map_dashcam_missing_reason_code(normalized_error=err) == "provider_rate_limited"


def test_timeout_code() -> None:
    err = _make_error(code="DASHCAM_TIMEOUT")
    assert map_dashcam_missing_reason_code(normalized_error=err) == "provider_timeout"


def test_auth_failed_code() -> None:
    err = _make_error(code="DASHCAM_AUTH_FAILED")
    assert map_dashcam_missing_reason_code(normalized_error=err) == "provider_auth_failed"


def test_stream_unavailable_code() -> None:
    err = _make_error(code="DASHCAM_STREAM_UNAVAILABLE")
    assert map_dashcam_missing_reason_code(normalized_error=err) == "provider_unavailable"


def test_generic_provider_error_fallback() -> None:
    err = _make_error(code="SOMETHING_ELSE", operator_message="unrelated failure")
    assert map_dashcam_missing_reason_code(normalized_error=err) == "provider_error"


def test_no_inputs_returns_provider_error() -> None:
    # Neither error nor operator_message — must still return canonical fallback.
    assert map_dashcam_missing_reason_code() == "provider_error"


def test_operator_message_takes_precedence_over_error_message() -> None:
    err = _make_error(code="", operator_message="should not be used")
    assert (
        map_dashcam_missing_reason_code(
            normalized_error=err, operator_message="camera mapping missing"
        )
        == "camera_not_mapped"
    )


def test_operator_message_is_case_insensitive() -> None:
    err = _make_error()
    assert (
        map_dashcam_missing_reason_code(
            normalized_error=err, operator_message="MAPPING NOT FOUND"
        )
        == "camera_not_mapped"
    )


def test_code_lowercase_is_normalised_to_uppercase() -> None:
    err = _make_error(code="dashcam_rate_limited")
    assert map_dashcam_missing_reason_code(normalized_error=err) == "provider_rate_limited"


# --- dashcam_reason_message ---


def test_dashcam_reason_message_returns_empty_for_falsy() -> None:
    assert dashcam_reason_message(None) == ""
    assert dashcam_reason_message("") == ""


def test_dashcam_reason_message_unknown_code_falls_back_to_code() -> None:
    assert dashcam_reason_message("unknown_code") == "unknown_code"


def test_dashcam_reason_message_covers_all_known_codes() -> None:
    for code, expected in REASON_MESSAGES.items():
        assert dashcam_reason_message(code) == expected

