"""Integration-layer normalized error types and mappers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import httpx


ErrorCategory = Literal["telematics", "dashcam", "messaging", "mapping", "auth", "storage", "integration"]

# Canonical code sets by integration domain.
TELEMATICS_ERROR_CODES = frozenset(
    {
        "TELEMATICS_AUTH_FAILED",
        "TELEMATICS_RATE_LIMITED",
        "TELEMATICS_TIMEOUT",
        "TELEMATICS_UNAVAILABLE",
        "TELEMATICS_NOT_MAPPED",
        "TELEMATICS_DATA_NOT_AVAILABLE",
        "TELEMATICS_PROVIDER_ERROR",
    }
)
DASHCAM_ERROR_CODES = frozenset(
    {
        "DASHCAM_AUTH_FAILED",
        "DASHCAM_RATE_LIMITED",
        "DASHCAM_TIMEOUT",
        "DASHCAM_STREAM_UNAVAILABLE",
        "DASHCAM_MEDIA_NOT_AVAILABLE",
        "DASHCAM_PROVIDER_ERROR",
    }
)
MESSAGING_ERROR_CODES = frozenset(
    {
        "MESSAGING_AUTH_FAILED",
        "MESSAGING_RATE_LIMITED",
        "MESSAGING_TIMEOUT",
        "MESSAGING_INVALID_DESTINATION",
        "MESSAGING_PROVIDER_ERROR",
    }
)
MAPPING_ERROR_CODES = frozenset(
    {
        "MAPPING_NOT_FOUND",
        "MAPPING_CONFLICT",
        "MAPPING_INVALID_REFERENCE",
        "MAPPING_PROVIDER_ERROR",
    }
)
AUTH_ERROR_CODES = frozenset(
    {
        "AUTH_INVALID_CREDENTIALS",
        "AUTH_EXPIRED_TOKEN",
        "AUTH_PROVIDER_UNAVAILABLE",
        "AUTH_PROVIDER_ERROR",
    }
)
STORAGE_ERROR_CODES = frozenset(
    {
        "STORAGE_INVALID_OBJECT_KEY",
        "STORAGE_TIMEOUT",
        "STORAGE_UNAVAILABLE",
        "STORAGE_PROVIDER_ERROR",
    }
)


@dataclass(frozen=True)
class NormalizedIntegrationError:
    code: str
    category: ErrorCategory
    provider_key: str
    retryable: bool
    user_facing_message: str
    operator_message: str

    def to_dict(self) -> dict[str, str | bool]:
        return asdict(self)


class IntegrationError(Exception):
    """Base integration error carrying normalized error metadata."""

    def __init__(self, normalized_error: NormalizedIntegrationError):
        super().__init__(normalized_error.operator_message)
        self.normalized_error = normalized_error


class ProviderNotRegisteredError(IntegrationError):
    """Raised when no provider is registered for a required capability."""


class CapabilityNotSupportedError(IntegrationError):
    """Raised when a provider does not implement a requested capability."""


class ProviderHealthError(IntegrationError):
    """Raised when a provider health check fails."""


def map_samsara_error(exc: Exception, *, category: ErrorCategory = "dashcam") -> NormalizedIntegrationError:
    if isinstance(exc, httpx.TimeoutException):
        code = "DASHCAM_TIMEOUT" if category == "dashcam" else "TELEMATICS_TIMEOUT"
        return NormalizedIntegrationError(
            code=code,
            category=category,
            provider_key="samsara",
            retryable=True,
            user_facing_message="Provider request timed out. Please retry shortly.",
            operator_message=str(exc),
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            code = "DASHCAM_AUTH_FAILED" if category == "dashcam" else "TELEMATICS_AUTH_FAILED"
            return NormalizedIntegrationError(code, category, "samsara", False, "Integration authorization failed.", str(exc))
        if status_code == 429:
            code = "DASHCAM_RATE_LIMITED" if category == "dashcam" else "TELEMATICS_RATE_LIMITED"
            return NormalizedIntegrationError(code, category, "samsara", True, "Provider rate limit reached. Please retry.", str(exc))
        return NormalizedIntegrationError(
            code="DASHCAM_PROVIDER_ERROR" if category == "dashcam" else "TELEMATICS_PROVIDER_ERROR",
            category=category,
            provider_key="samsara",
            retryable=status_code >= 500,
            user_facing_message="Provider request failed.",
            operator_message=str(exc),
        )
    message = str(exc).lower()
    if "no footage" in message or "not_found" in message:
        return NormalizedIntegrationError(
            code="DASHCAM_MEDIA_NOT_AVAILABLE",
            category="dashcam",
            provider_key="samsara",
            retryable=False,
            user_facing_message="Dashcam media was not available for the requested time window.",
            operator_message=str(exc),
        )
    return NormalizedIntegrationError(
        code="DASHCAM_STREAM_UNAVAILABLE" if category == "dashcam" else "TELEMATICS_UNAVAILABLE",
        category=category,
        provider_key="samsara",
        retryable=True,
        user_facing_message="Provider is temporarily unavailable.",
        operator_message=str(exc),
    )


def map_twilio_error(exc: Exception, *, category: ErrorCategory = "messaging") -> NormalizedIntegrationError:
    provider_key = "twilio"
    if isinstance(exc, httpx.TimeoutException):
        return NormalizedIntegrationError(
            code="MESSAGING_TIMEOUT" if category != "auth" else "AUTH_PROVIDER_UNAVAILABLE",
            category=category,
            provider_key=provider_key,
            retryable=True,
            user_facing_message="Messaging service timed out. Please retry.",
            operator_message=str(exc),
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            code = "AUTH_PROVIDER_ERROR" if category == "auth" else "MESSAGING_AUTH_FAILED"
            return NormalizedIntegrationError(code, category, provider_key, False, "Provider authentication failed.", str(exc))
        if status_code == 429:
            return NormalizedIntegrationError("MESSAGING_RATE_LIMITED", category, provider_key, True, "Messaging provider rate limit reached.", str(exc))
        if status_code == 400:
            return NormalizedIntegrationError("MESSAGING_INVALID_DESTINATION", category, provider_key, False, "The destination phone number is invalid.", str(exc))
    if isinstance(exc, ValueError):
        return NormalizedIntegrationError(
            code="MESSAGING_INVALID_DESTINATION",
            category=category,
            provider_key=provider_key,
            retryable=False,
            user_facing_message="The destination phone number is invalid or unsupported.",
            operator_message=str(exc),
        )
    return NormalizedIntegrationError(
        code="MESSAGING_PROVIDER_ERROR" if category != "auth" else "AUTH_PROVIDER_ERROR",
        category=category,
        provider_key=provider_key,
        retryable=True,
        user_facing_message="Messaging provider operation failed.",
        operator_message=str(exc),
    )


def map_storage_error(exc: Exception, *, provider_key: str = "storage") -> NormalizedIntegrationError:
    from app.services.vault_s3 import S3ObjectKeyValidationError, S3PresignGenerationError

    if isinstance(exc, S3ObjectKeyValidationError):
        return NormalizedIntegrationError(
            code="STORAGE_INVALID_OBJECT_KEY",
            category="storage",
            provider_key=provider_key,
            retryable=False,
            user_facing_message="Storage key validation failed.",
            operator_message=str(exc),
        )
    if isinstance(exc, S3PresignGenerationError):
        return NormalizedIntegrationError(
            code="STORAGE_UNAVAILABLE",
            category="storage",
            provider_key=provider_key,
            retryable=True,
            user_facing_message="Storage service unavailable.",
            operator_message=str(exc),
        )
    return NormalizedIntegrationError(
        code="STORAGE_PROVIDER_ERROR",
        category="storage",
        provider_key=provider_key,
        retryable=True,
        user_facing_message="Storage operation failed.",
        operator_message=str(exc),
    )


def as_normalized_error(exc: Exception, *, provider_hint: str | None = None, category: ErrorCategory = "integration") -> NormalizedIntegrationError:
    if isinstance(exc, IntegrationError):
        return exc.normalized_error
    if provider_hint == "samsara":
        return map_samsara_error(exc, category=category)
    if provider_hint == "twilio":
        return map_twilio_error(exc, category=category)
    if provider_hint in {"s3", "storage"}:
        return map_storage_error(exc, provider_key=provider_hint)
    return NormalizedIntegrationError(
        code="INTEGRATION_PROVIDER_ERROR",
        category=category,
        provider_key=provider_hint or "unknown",
        retryable=True,
        user_facing_message="An integration error occurred.",
        operator_message=str(exc),
    )
