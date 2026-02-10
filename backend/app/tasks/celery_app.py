"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "adc_mvp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "app.tasks.evidence_tasks.capture_dashcam": {"queue": "evidence"},
        "app.tasks.evidence_tasks.capture_telematics_bundle": {"queue": "evidence"},
        "app.tasks.export_tasks.build_export": {"queue": "exports"},
        "app.tasks.notify_tasks.notify_safety": {"queue": "notifications"},
    },
)


# ── Hello-world smoke-test task ─────────────────────────────────────


@celery_app.task
def hello_world():
    """Minimal task used to verify that the Celery worker is wired up."""
    return {"message": "hello world", "status": "ok"}
