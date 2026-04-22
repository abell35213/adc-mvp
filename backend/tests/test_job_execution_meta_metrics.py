"""Tests for retry scheduler stuck metric emission."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, JobExecutionMeta
from app.db.repo import job_execution_meta as job_execution_meta_repo
from app.jobs import tracking


def _build_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_record_task_started_does_not_emit_stuck_metric(monkeypatch):
    calls: list[str] = []

    def _capture(metric_name: str) -> None:
        calls.append(metric_name)

    monkeypatch.setattr(tracking, "increment", _capture)
    monkeypatch.setattr(tracking, "upsert_job_execution_meta", lambda **_: None)

    tracking.record_task_started(
        task_name="app.tasks.evidence.capture",
        task_id="task-123",
        max_retries=3,
    )

    assert calls == []


def test_list_ops_jobs_emits_stuck_metric_for_stale_running_tasks(monkeypatch):
    db = _build_session()
    try:
        stale_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=31)
        row = JobExecutionMeta(
            celery_task_id="task-456",
            task_name="app.tasks.evidence.capture",
            task_type="evidence_capture",
            status="running",
            retry_count=0,
            last_heartbeat_at_utc=stale_heartbeat,
            started_at_utc=stale_heartbeat,
        )
        db.add(row)
        db.commit()

        calls: list[str] = []

        def _capture(metric_name: str) -> None:
            calls.append(metric_name)

        monkeypatch.setattr(job_execution_meta_repo, "increment", _capture)

        results = job_execution_meta_repo.list_ops_jobs_with_db(
            db=db,
            statuses={"running", "retrying", "failed"},
            stale_after_minutes=15,
        )

        assert any(item.status == "stuck" for item in results)
        assert calls == ["retry.scheduler.stuck_in_progress"]
    finally:
        db.close()
