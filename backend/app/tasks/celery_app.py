"""Celery application configuration."""

from celery import Celery
from celery.signals import task_failure, task_prerun

from app.core.config import settings
from app.core.logging import clear_log_context, set_log_context, set_request_id
from app.core.metrics import MetricNames, increment

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
        "app.tasks.notification_tasks.notify_safety_manager": {
            "queue": "notifications"
        },
        "app.tasks.notify_tasks.notify_safety": {"queue": "notifications"},
    },
)


@task_prerun.connect
def _on_task_prerun(*_, task=None, **__):
    headers = getattr(task.request, "headers", {}) or {}
    set_request_id(headers.get("x-request-id"))
    set_log_context(
        user_id=headers.get("x-user-id") or None,
        org_id=headers.get("x-org-id") or None,
    )
    increment(MetricNames.CELERY_TASK_STARTED)


@task_failure.connect
def _on_task_failure(*_, **__):
    increment(MetricNames.CELERY_TASK_FAILURES)
    clear_log_context()


@celery_app.task
def hello_world():
    """Minimal task used to verify that the Celery worker is wired up."""
    return {"message": "hello world", "status": "ok"}
