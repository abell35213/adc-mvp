"""Tests for job retry categorization and policy behavior."""

import httpx

from app.jobs.retry_policy import (
    classify_retry_exception,
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
    assert classify_retry_exception(exc) == "transient_dependency"


def test_classify_retry_exception_optional_artifact_failure() -> None:
    exc = RuntimeError("Optional artifact skipped due to extension_not_allowed")
    assert classify_retry_exception(exc) == "optional_artifact_inclusion_failure"


def test_should_retry_policy_enforced_per_task_type() -> None:
    assert should_retry("notification_tasks", "transient_dependency", retry_count=1)
    assert not should_retry(
        "notification_tasks", "internal_processing_error", retry_count=1
    )
    assert not should_retry(
        "export_tasks", "optional_artifact_inclusion_failure", retry_count=0
    )
