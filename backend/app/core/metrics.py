"""Backward-compatible metrics imports and integration metric definitions."""

from app.observability.metrics import MetricNames as _BaseMetricNames
from app.observability.metrics import increment, timed


class MetricNames(_BaseMetricNames):
    """Canonical metric names for integration reliability instrumentation."""

    INTEGRATION_PROVIDER_REQUESTS = "integration.provider.requests"
    INTEGRATION_PROVIDER_SUCCESS = "integration.provider.success"
    INTEGRATION_PROVIDER_FAILURE = "integration.provider.failure"
    INTEGRATION_PROVIDER_TIMEOUT = "integration.provider.timeout"
    INTEGRATION_PROVIDER_RATE_LIMIT = "integration.provider.rate_limit"
    INTEGRATION_PROVIDER_AUTH_FAILURE = "integration.provider.auth_failure"
    INTEGRATION_PROVIDER_LATENCY = "integration.provider.latency"

    EVIDENCE_COMPLETION_TIME = "integration.evidence.completion_time"
    EVIDENCE_PARTIAL_RESULT = "integration.evidence.partial"
    EVIDENCE_UNAVAILABLE_RESULT = "integration.evidence.unavailable"

    OTP_DELIVERY_ATTEMPTS = "otp.delivery.attempts"
    OTP_DELIVERY_SUCCESS = "otp.delivery.success"
    OTP_DELIVERY_FAILURE = "otp.delivery.failure"
    OTP_DELIVERY_TIMEOUT = "otp.delivery.timeout"
    OTP_DELIVERY_RATE_LIMIT = "otp.delivery.rate_limit"
    OTP_DELIVERY_AUTH_FAILURE = "otp.delivery.auth_failure"

    WEBHOOK_SIGNATURE_FAILURES = "webhook.signature.failures"
    RETRY_SCHEDULER_QUEUED = "retry.scheduler.queued"
    RETRY_SCHEDULER_RETRYING = "retry.scheduler.retrying"
    RETRY_SCHEDULER_TERMINAL_FAILURES = "retry.scheduler.terminal_failures"
    RETRY_SCHEDULER_STUCK_IN_PROGRESS = "retry.scheduler.stuck_in_progress"


__all__ = ["MetricNames", "increment", "timed"]
