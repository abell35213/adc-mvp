"""Tests for job retry categorization and policy behavior."""

import httpx

from app.integrations.errors import NormalizedIntegrationError
from app.jobs.retry_policy import (
    classify_normalized_error,
    classify_retry_exception,
    compute_retry_delay_seconds,
    get_policy_for_capability,
    resolve_task_type,
    should_retry,
)


def test_resolve_task_type_from_name() -> None:
    assert resolve_task_type("app.tasks.export_tasks.build_export") == "export_tasks"
    assert (
        resolve_task_type("app.tasks.evidence_tasks.capture_dashcam")
        == "evidence_tasks"
    )
    assert (
        resolve_task_type("app.tasks.notification_tasks.notify_safety_manager")
        == "notification_tasks"
    )


def test_classify_retry_exception_transient_dependency() -> None:
    exc = httpx.ReadTimeout("provider timed out")
    assert classify_retry_exception(exc) == "retryable_transient"


def test_classify_retry_exception_non_retryable_intervention_marker() -> None:
    exc = RuntimeError("credentials_invalid")
    assert classify_retry_exception(exc) == "non_retryable_intervention_required"


def test_classify_normalized_error_non_retryable_for_mapping() -> None:
    err = NormalizedIntegrationError(
        code="TELEMATICS_NOT_MAPPED",
        category="telematics",
        provider_key="samsara",
        retryable=False,
        user_facing_message="missing mapping",
        operator_message="vehicle_mapping_missing",
    )
    assert classify_normalized_error(err) == "non_retryable_intervention_required"


def test_should_retry_policy_enforced_per_task_type() -> None:
    assert should_retry("notification_tasks", "retryable_transient", retry_count=1)
    assert should_retry("export_tasks", "conditionally_retryable", retry_count=1)
    assert not should_retry(
        "evidence_tasks", "non_retryable_intervention_required", retry_count=0
    )


def test_backoff_delay_respects_capability_policy_ceiling() -> None:
    policy = get_policy_for_capability("telematics")
    delay = compute_retry_delay_seconds(retry_count=10, policy=policy)
    assert delay <= int(policy.backoff_cap_seconds * (1 + policy.jitter_ratio))
