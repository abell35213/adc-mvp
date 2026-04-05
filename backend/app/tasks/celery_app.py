"""Celery application configuration."""

import logging

from celery import Celery
from celery.signals import task_failure

from app.core.config import settings
from app.core.logging import clear_log_context, set_log_context, set_request_id
from app.core.metrics import MetricNames, increment

logger = logging.getLogger(__name__)

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
    worker_prefetch_multiplier=1,
    task_default_retry_delay=30,
    broker_transport_options={
        "visibility_timeout": 3600,
    },
    task_create_missing_queues=True,
    task_routes={
        "app.tasks.evidence_tasks.capture_dashcam": {"queue": "evidence"},
        "app.tasks.evidence_tasks.capture_telematics_bundle": {"queue": "evidence"},
        "app.tasks.export_tasks.build_export": {"queue": "exports"},
        "app.tasks.notification_tasks.notify_safety_manager": {
            "queue": "notifications"
        },
        "app.tasks.notify_tasks.notify_safety": {"queue": "notifications"},
        "app.tasks.celery_app.record_dead_letter": {"queue": "dead_letter"},
    },
    task_annotations={
        "app.tasks.evidence_tasks.capture_dashcam": {
            "autoretry_for": (Exception,),
            "retry_backoff": True,
            "retry_backoff_max": 300,
            "retry_jitter": True,
        },
        "app.tasks.evidence_tasks.capture_telematics_bundle": {
            "autoretry_for": (Exception,),
            "retry_backoff": True,
            "retry_backoff_max": 300,
            "retry_jitter": True,
        },
        "app.tasks.export_tasks.build_export": {
            "autoretry_for": (Exception,),
            "retry_backoff": True,
            "retry_backoff_max": 180,
            "retry_jitter": True,
        },
        "app.tasks.notification_tasks.notify_safety_manager": {
            "autoretry_for": (Exception,),
            "retry_backoff": True,
            "retry_backoff_max": 120,
            "retry_jitter": True,
        },
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


@celery_app.task(name="app.tasks.celery_app.record_dead_letter")
def record_dead_letter(payload: dict):
    """Persist terminal task failure payload to a dead-letter queue."""
    logger.error("Dead-letter task received: %s", payload)
    return {"status": "recorded", "task_name": payload.get("task_name")}


@task_failure.connect
def route_terminal_failures_to_dead_letter(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    einfo=None,
    **extra,
):
    """Push non-retriable terminal failures to a dedicated dead-letter queue."""
    if sender is None:
        return
    max_retries = getattr(sender, "max_retries", 0) or 0
    current_retries = getattr(getattr(sender, "request", None), "retries", 0) or 0
    if current_retries < max_retries:
        return

    payload = {
        "task_name": getattr(sender, "name", "unknown"),
        "task_id": task_id,
        "args": list(args or []),
        "kwargs": kwargs or {},
        "exception": str(exception),
    }
    logger.error("Routing task failure to dead-letter queue: %s", payload)
    celery_app.send_task(
        "app.tasks.celery_app.record_dead_letter",
        kwargs={"payload": payload},
        queue="dead_letter",
    )
