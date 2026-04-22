"""Repository helpers for persistent job execution metadata."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.metrics import MetricNames, increment
from app.db.models import JobExecutionMeta
from app.db.session import SessionLocal


@contextmanager
def _session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def upsert_job_execution_meta(
    *,
    task_id: str,
    task_name: str,
    task_type: str,
    status: str,
    retry_count: int | None = None,
    max_retries: int | None = None,
    retry_category: str | None = None,
    should_retry: bool | None = None,
    next_retry_at_utc: datetime | None = None,
    started_at_utc: datetime | None = None,
    finished_at_utc: datetime | None = None,
    last_heartbeat_at_utc: datetime | None = None,
    last_error: str | None = None,
    args_json: list[Any] | None = None,
    kwargs_json: dict[str, Any] | None = None,
) -> JobExecutionMeta:
    with _session_scope() as db:
        return upsert_job_execution_meta_with_db(
            db=db,
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            status=status,
            retry_count=retry_count,
            max_retries=max_retries,
            retry_category=retry_category,
            should_retry=should_retry,
            next_retry_at_utc=next_retry_at_utc,
            started_at_utc=started_at_utc,
            finished_at_utc=finished_at_utc,
            last_heartbeat_at_utc=last_heartbeat_at_utc,
            last_error=last_error,
            args_json=args_json,
            kwargs_json=kwargs_json,
        )


def upsert_job_execution_meta_with_db(
    *,
    db,
    task_id: str,
    task_name: str,
    task_type: str,
    status: str,
    retry_count: int | None = None,
    max_retries: int | None = None,
    retry_category: str | None = None,
    should_retry: bool | None = None,
    next_retry_at_utc: datetime | None = None,
    started_at_utc: datetime | None = None,
    finished_at_utc: datetime | None = None,
    last_heartbeat_at_utc: datetime | None = None,
    last_error: str | None = None,
    args_json: list[Any] | None = None,
    kwargs_json: dict[str, Any] | None = None,
) -> JobExecutionMeta:
    row = (
        db.query(JobExecutionMeta)
        .filter(JobExecutionMeta.celery_task_id == task_id)
        .with_for_update()
        .first()
    )
    if row is None:
        row = JobExecutionMeta(
            celery_task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            status=status,
            retry_count=retry_count or 0,
            max_retries=max_retries,
            retry_category=retry_category,
            should_retry=bool(should_retry) if should_retry is not None else None,
            next_retry_at_utc=next_retry_at_utc,
            started_at_utc=started_at_utc,
            finished_at_utc=finished_at_utc,
            last_heartbeat_at_utc=last_heartbeat_at_utc,
            last_error=last_error,
            args_json=args_json or [],
            kwargs_json=kwargs_json or {},
        )
        db.add(row)
        db.flush()
        db.refresh(row)
        return row

    row.task_name = task_name
    row.task_type = task_type
    row.status = status
    if retry_count is not None:
        row.retry_count = retry_count
    if max_retries is not None:
        row.max_retries = max_retries
    if retry_category is not None:
        row.retry_category = retry_category
    if should_retry is not None:
        row.should_retry = should_retry
    if next_retry_at_utc is not None or status != "retrying":
        row.next_retry_at_utc = next_retry_at_utc
    if started_at_utc is not None:
        row.started_at_utc = started_at_utc
    if finished_at_utc is not None:
        row.finished_at_utc = finished_at_utc
    if last_heartbeat_at_utc is not None:
        row.last_heartbeat_at_utc = last_heartbeat_at_utc
    if last_error is not None or status == "succeeded":
        row.last_error = last_error
    if args_json is not None:
        row.args_json = args_json
    if kwargs_json is not None:
        row.kwargs_json = kwargs_json
    db.flush()
    db.refresh(row)
    return row


def list_ops_jobs(
    *, statuses: set[str], stale_after_minutes: int = 15
) -> list[JobExecutionMeta]:
    with _session_scope() as db:
        return list_ops_jobs_with_db(
            db=db, statuses=statuses, stale_after_minutes=stale_after_minutes
        )


def list_ops_jobs_with_db(
    *, db, statuses: set[str], stale_after_minutes: int = 15
) -> list[JobExecutionMeta]:
    rows = (
        db.query(JobExecutionMeta).filter(JobExecutionMeta.status.in_(statuses)).all()
    )
    stale_threshold = datetime.now(timezone.utc) - timedelta(
        minutes=stale_after_minutes
    )
    for row in rows:
        if (
            row.status in {"queued", "running", "retrying"}
            and row.last_heartbeat_at_utc
        ):
            heartbeat = row.last_heartbeat_at_utc
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            if heartbeat < stale_threshold:
                if row.status != "stuck":
                    row.status = "stuck"
                    increment(MetricNames.RETRY_SCHEDULER_STUCK_IN_PROGRESS)
                    db.flush()
    return (
        db.query(JobExecutionMeta)
        .filter(JobExecutionMeta.status.in_(statuses | {"stuck"}))
        .order_by(JobExecutionMeta.updated_at_utc.desc())
        .all()
    )


def summarize_ops_jobs(*, stale_after_minutes: int = 15) -> dict[str, int]:
    with _session_scope() as db:
        return summarize_ops_jobs_with_db(
            db=db, stale_after_minutes=stale_after_minutes
        )


def summarize_ops_jobs_with_db(*, db, stale_after_minutes: int = 15) -> dict[str, int]:
    rows = list_ops_jobs_with_db(
        db=db,
        statuses={"failed", "retrying", "running", "queued"},
        stale_after_minutes=stale_after_minutes,
    )
    summary = {"failed": 0, "retrying": 0, "stuck": 0}
    for row in rows:
        if row.status in summary:
            summary[row.status] += 1
    return summary
