"""Retry classification and policy decisions for Celery jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

RetryCategory = Literal[
    "transient_dependency",
    "internal_processing_error",
    "optional_artifact_inclusion_failure",
]
TaskType = Literal["export_tasks", "evidence_tasks", "notification_tasks", "unknown"]


@dataclass(frozen=True)
class RetryPolicy:
    """Policy controls for a job task class."""

    max_retries: int
    retryable_categories: frozenset[RetryCategory]


TASK_TYPE_POLICY: dict[TaskType, RetryPolicy] = {
    "export_tasks": RetryPolicy(
        max_retries=3,
        retryable_categories=frozenset(
            {"transient_dependency", "internal_processing_error"}
        ),
    ),
    "evidence_tasks": RetryPolicy(
        max_retries=3,
        retryable_categories=frozenset(
            {"transient_dependency", "internal_processing_error"}
        ),
    ),
    "notification_tasks": RetryPolicy(
        max_retries=2,
        retryable_categories=frozenset({"transient_dependency"}),
    ),
    "unknown": RetryPolicy(
        max_retries=0,
        retryable_categories=frozenset(),
    ),
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


def classify_retry_exception(exc: BaseException) -> RetryCategory:
    """Classify task exception into an operational retry category."""
    message = str(exc).lower()

    if isinstance(exc, (httpx.HTTPError, TimeoutError, ConnectionError, OSError)):
        return "transient_dependency"

    optional_markers = (
        "optional artifact",
        "artifact_missing_from_s3",
        "extension_not_allowed",
        "artifact skipped",
    )
    if any(marker in message for marker in optional_markers):
        return "optional_artifact_inclusion_failure"

    return "internal_processing_error"


def should_retry(
    task_type: TaskType, category: RetryCategory, retry_count: int
) -> bool:
    """Return whether the policy allows an additional retry attempt."""
    policy = TASK_TYPE_POLICY.get(task_type, TASK_TYPE_POLICY["unknown"])
    if category not in policy.retryable_categories:
        return False
    return retry_count < policy.max_retries
