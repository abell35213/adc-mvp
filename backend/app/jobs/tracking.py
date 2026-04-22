"""Persistent Celery job execution metadata tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.metrics import MetricNames, increment
from app.db.repo.job_execution_meta import upsert_job_execution_meta
from app.jobs.retry_policy import (
    classify_retry_exception,
    get_policy_for_task,
    resolve_task_type,
    should_retry,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def record_task_queued(
    *,
    task_name: str,
    task_id: str,
    args: list[Any] | None,
    kwargs: dict[str, Any] | None,
) -> None:
    increment(MetricNames.RETRY_SCHEDULER_QUEUED)
    upsert_job_execution_meta(
        task_id=task_id,
        task_name=task_name,
        task_type=resolve_task_type(task_name),
        status="queued",
        args_json=args or [],
        kwargs_json=kwargs or {},
        last_heartbeat_at_utc=utc_now(),
    )


def record_task_started(*, task_name: str, task_id: str, max_retries: int) -> None:
    increment(MetricNames.RETRY_SCHEDULER_STUCK_IN_PROGRESS)
    upsert_job_execution_meta(
        task_id=task_id,
        task_name=task_name,
        task_type=resolve_task_type(task_name),
        status="running",
        max_retries=max_retries,
        started_at_utc=utc_now(),
        last_heartbeat_at_utc=utc_now(),
    )


def record_task_retrying(
    *,
    task_name: str,
    task_id: str,
    retry_count: int,
    max_retries: int,
    exception: BaseException,
) -> None:
    task_type = resolve_task_type(task_name)
    retry_class = classify_retry_exception(exception)
    will_retry = should_retry(task_type, retry_class, retry_count)
    status = "retrying" if will_retry else "failed"
    if will_retry:
        increment(MetricNames.RETRY_SCHEDULER_RETRYING)
    else:
        increment(MetricNames.RETRY_SCHEDULER_TERMINAL_FAILURES)
    policy = get_policy_for_task(task_name)
    delay_seconds = policy.base_delay_seconds * (2 ** max(retry_count, 0))
    delay_seconds = min(delay_seconds, policy.backoff_cap_seconds)
    next_retry = utc_now() + timedelta(seconds=delay_seconds) if will_retry else None
    upsert_job_execution_meta(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status=status,
        retry_count=retry_count,
        max_retries=max_retries,
        retry_category=retry_class,
        should_retry=will_retry,
        next_retry_at_utc=next_retry,
        last_error=str(exception),
        last_heartbeat_at_utc=utc_now(),
        finished_at_utc=utc_now() if not will_retry else None,
    )


def record_task_failed(
    *,
    task_name: str,
    task_id: str,
    retry_count: int,
    max_retries: int,
    exception: BaseException,
) -> None:
    increment(MetricNames.RETRY_SCHEDULER_TERMINAL_FAILURES)
    task_type = resolve_task_type(task_name)
    retry_class = classify_retry_exception(exception)
    upsert_job_execution_meta(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        status="failed",
        retry_count=retry_count,
        max_retries=max_retries,
        retry_category=retry_class,
        should_retry=False,
        last_error=str(exception),
        finished_at_utc=utc_now(),
        last_heartbeat_at_utc=utc_now(),
    )


def record_task_succeeded(*, task_name: str, task_id: str) -> None:
    upsert_job_execution_meta(
        task_id=task_id,
        task_name=task_name,
        task_type=resolve_task_type(task_name),
        status="succeeded",
        should_retry=False,
        finished_at_utc=utc_now(),
        last_heartbeat_at_utc=utc_now(),
        last_error=None,
    )
