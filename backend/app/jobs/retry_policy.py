"""Retry classification and policy decisions for Celery jobs."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import cast
from typing import Literal

import httpx

from app.integrations.errors import NormalizedIntegrationError

RetryClass = Literal[
    "retryable_transient",
    "conditionally_retryable",
    "non_retryable_intervention_required",
]
TaskType = Literal["export_tasks", "evidence_tasks", "notification_tasks", "unknown"]
Capability = Literal[
    "dashcam", "telematics", "messaging", "export", "inspections", "unknown"
]


@dataclass(frozen=True)
class RetryPolicy:
    """Policy controls for a job task class/capability."""

    max_retries: int
    base_delay_seconds: int
    backoff_cap_seconds: int
    jitter_ratio: float


TASK_TYPE_POLICY: dict[TaskType, RetryPolicy] = {
    "export_tasks": RetryPolicy(max_retries=3, base_delay_seconds=15, backoff_cap_seconds=180, jitter_ratio=0.25),
    "evidence_tasks": RetryPolicy(max_retries=4, base_delay_seconds=20, backoff_cap_seconds=300, jitter_ratio=0.3),
    "notification_tasks": RetryPolicy(max_retries=2, base_delay_seconds=10, backoff_cap_seconds=120, jitter_ratio=0.2),
    "unknown": RetryPolicy(max_retries=0, base_delay_seconds=30, backoff_cap_seconds=60, jitter_ratio=0.0),
}

CAPABILITY_POLICY: dict[Capability, RetryPolicy] = {
    "dashcam": RetryPolicy(max_retries=4, base_delay_seconds=20, backoff_cap_seconds=300, jitter_ratio=0.3),
    "telematics": RetryPolicy(max_retries=3, base_delay_seconds=30, backoff_cap_seconds=420, jitter_ratio=0.35),
    "messaging": RetryPolicy(max_retries=2, base_delay_seconds=10, backoff_cap_seconds=120, jitter_ratio=0.2),
    "export": RetryPolicy(max_retries=3, base_delay_seconds=15, backoff_cap_seconds=180, jitter_ratio=0.2),
    "inspections": RetryPolicy(max_retries=3, base_delay_seconds=30, backoff_cap_seconds=420, jitter_ratio=0.35),
    "unknown": RetryPolicy(max_retries=0, base_delay_seconds=30, backoff_cap_seconds=60, jitter_ratio=0.0),
}


RETRYABLE_TRANSIENT_CODES = frozenset(
    {
        "TELEMATICS_TIMEOUT",
        "TELEMATICS_UNAVAILABLE",
        "TELEMATICS_RATE_LIMITED",
        "DASHCAM_TIMEOUT",
        "DASHCAM_STREAM_UNAVAILABLE",
        "DASHCAM_RATE_LIMITED",
        "MESSAGING_TIMEOUT",
        "MESSAGING_RATE_LIMITED",
        "STORAGE_TIMEOUT",
        "STORAGE_UNAVAILABLE",
    }
)

CONDITIONALLY_RETRYABLE_CODES = frozenset(
    {
        "TELEMATICS_PROVIDER_ERROR",
        "DASHCAM_PROVIDER_ERROR",
        "MESSAGING_PROVIDER_ERROR",
        "AUTH_PROVIDER_UNAVAILABLE",
        "AUTH_EXPIRED_TOKEN",
    }
)

NON_RETRYABLE_INTERVENTION_CODES = frozenset(
    {
        "AUTH_INVALID_CREDENTIALS",
        "TELEMATICS_AUTH_FAILED",
        "DASHCAM_AUTH_FAILED",
        "MESSAGING_AUTH_FAILED",
        "TELEMATICS_NOT_MAPPED",
        "MAPPING_NOT_FOUND",
        "MAPPING_INVALID_REFERENCE",
    }
)

INTERVENTION_OPERATOR_MARKERS = {
    "credentials_invalid",
    "vehicle_mapping_missing",
}


def resolve_task_type(task_name: str) -> TaskType:
    """Map a fully qualified Celery task name to a tracked task class."""
    if ".export_tasks." in task_name:
        return "export_tasks"
    if ".evidence_tasks." in task_name:
        return "evidence_tasks"
    if ".notification_tasks." in task_name or ".notify_tasks." in task_name:
        return "notification_tasks"
    return "unknown"


def classify_retry_exception(exc: BaseException) -> RetryClass:
    """Classify task exception into retry classes when no normalized code is present."""
    message = str(exc).lower()

    if isinstance(exc, (httpx.HTTPError, TimeoutError, ConnectionError, OSError)):
        return "retryable_transient"

    if any(marker in message for marker in INTERVENTION_OPERATOR_MARKERS):
        return "non_retryable_intervention_required"

    optional_markers = (
        "optional artifact",
        "artifact_missing_from_s3",
        "extension_not_allowed",
        "artifact skipped",
    )
    if any(marker in message for marker in optional_markers):
        return "conditionally_retryable"

    return "conditionally_retryable"


def classify_normalized_error(error: NormalizedIntegrationError) -> RetryClass:
    """Classify retries from canonical integration error codes and categories."""
    if error.code in NON_RETRYABLE_INTERVENTION_CODES:
        return "non_retryable_intervention_required"
    if error.code in RETRYABLE_TRANSIENT_CODES:
        return "retryable_transient"
    if error.code in CONDITIONALLY_RETRYABLE_CODES:
        return "conditionally_retryable"
    if not error.retryable:
        return "non_retryable_intervention_required"
    return "conditionally_retryable"


def should_retry(task_type: TaskType, retry_class: RetryClass, retry_count: int) -> bool:
    """Return whether the policy allows an additional retry attempt."""
    if retry_class == "non_retryable_intervention_required":
        return False
    policy = TASK_TYPE_POLICY.get(task_type, TASK_TYPE_POLICY["unknown"])
    return retry_count < policy.max_retries


def compute_retry_delay_seconds(*, retry_count: int, policy: RetryPolicy) -> int:
    """Exponential backoff + jitter delay for the next retry attempt."""
    exponential = min(policy.base_delay_seconds * (2**max(retry_count, 0)), policy.backoff_cap_seconds)
    if policy.jitter_ratio <= 0:
        return exponential
    spread = max(int(exponential * policy.jitter_ratio), 1)
    return max(1, exponential + random.randint(-spread, spread))


def get_policy_for_task(task_name: str) -> RetryPolicy:
    """Return policy for a task name."""
    return TASK_TYPE_POLICY.get(resolve_task_type(task_name), TASK_TYPE_POLICY["unknown"])


def get_policy_for_capability(capability: str | None) -> RetryPolicy:
    """Return retry/backoff policy for an integration capability."""
    key: Capability = cast(Capability, capability) if capability in CAPABILITY_POLICY else "unknown"
    return CAPABILITY_POLICY[key]


def next_retry_eta(*, retry_count: int, policy: RetryPolicy, now) -> object:
    """Calculate next retry ETA using a timezone-aware now() provider."""
    return now + timedelta(seconds=compute_retry_delay_seconds(retry_count=retry_count, policy=policy))
