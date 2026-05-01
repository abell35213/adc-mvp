"""Celery application configuration."""

import logging

from celery import Celery
from celery.signals import (
    before_task_publish,
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    worker_process_init,
)

from app.core.config import settings
from app.observability.alerts import init_sentry
from app.observability.metrics import MetricNames, increment
from app.observability.tracing import (
    ORG_ID_HEADER,
    USER_ID_HEADER,
    clear_context,
    extract_correlation_headers,
    inject_correlation_headers,
    set_actor_context,
    set_correlation_id,
)
from app.jobs.tracking import (
    record_task_failed,
    record_task_queued,
    record_task_retrying,
    record_task_started,
    record_task_succeeded,
)
from app.jobs.retry_policy import get_policy_for_capability
from app.observability.redaction import redact_log_data

logger = logging.getLogger(__name__)

celery_app = Celery(
    "adc_mvp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

dashcam_retry_policy = get_policy_for_capability("dashcam")
telematics_retry_policy = get_policy_for_capability("telematics")
export_retry_policy = get_policy_for_capability("export")
messaging_retry_policy = get_policy_for_capability("messaging")

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
        "app.tasks.crash_packet_tasks.dispatch_crash_packet": {
            "queue": "notifications"
        },
        "app.tasks.crash_packet_tasks.crash_packet_sla_watchdog": {
            "queue": "notifications"
        },
        "app.tasks.tms_sync_tasks.sync_tms_org": {"queue": "evidence"},
        "app.tasks.tms_sync_tasks.sync_tms_connection": {"queue": "evidence"},
        "app.tasks.celery_app.record_dead_letter": {"queue": "dead_letter"},
    },
    task_annotations={
        "app.tasks.evidence_tasks.capture_dashcam": {
            "max_retries": dashcam_retry_policy.max_retries,
            "retry_backoff": dashcam_retry_policy.base_delay_seconds,
            "retry_backoff_max": dashcam_retry_policy.backoff_cap_seconds,
            "retry_jitter": True,
        },
        "app.tasks.evidence_tasks.capture_telematics_bundle": {
            "max_retries": telematics_retry_policy.max_retries,
            "retry_backoff": telematics_retry_policy.base_delay_seconds,
            "retry_backoff_max": telematics_retry_policy.backoff_cap_seconds,
            "retry_jitter": True,
        },
        "app.tasks.export_tasks.build_export": {
            "autoretry_for": (Exception,),
            "max_retries": export_retry_policy.max_retries,
            "retry_backoff": export_retry_policy.base_delay_seconds,
            "retry_backoff_max": export_retry_policy.backoff_cap_seconds,
            "retry_jitter": True,
        },
        "app.tasks.notification_tasks.notify_safety_manager": {
            "autoretry_for": (Exception,),
            "max_retries": messaging_retry_policy.max_retries,
            "retry_backoff": messaging_retry_policy.base_delay_seconds,
            "retry_backoff_max": messaging_retry_policy.backoff_cap_seconds,
            "retry_jitter": True,
        },
        "app.tasks.crash_packet_tasks.dispatch_crash_packet": {
            "autoretry_for": (Exception,),
            "max_retries": messaging_retry_policy.max_retries,
            "retry_backoff": messaging_retry_policy.base_delay_seconds,
            "retry_backoff_max": messaging_retry_policy.backoff_cap_seconds,
            "retry_jitter": True,
        },
    },
)


@worker_process_init.connect
def _on_worker_process_init(**_kwargs):
    init_sentry(service="celery-worker")


@before_task_publish.connect
def _on_before_task_publish(headers=None, **_kwargs):
    if headers is None:
        return
    headers.update(inject_correlation_headers(headers))
    task_name = headers.get("task")
    task_id = headers.get("id")
    if task_name and task_id:
        record_task_queued(task_name=task_name, task_id=task_id, args=None, kwargs=None)


@task_prerun.connect
def _on_task_prerun(*_, task=None, **__):
    headers = getattr(task.request, "headers", {}) or {}
    extracted = extract_correlation_headers(headers)
    set_correlation_id(extracted.get("x-request-id"))
    set_actor_context(
        user_id=extracted.get(USER_ID_HEADER) or None,
        org_id=extracted.get(ORG_ID_HEADER) or None,
    )
    if task is not None:
        record_task_started(
            task_name=task.name,
            task_id=task.request.id,
            max_retries=getattr(task, "max_retries", 0) or 0,
        )
    increment(MetricNames.CELERY_TASK_STARTED)


@task_failure.connect
def _on_task_failure(*_, **__):
    increment(MetricNames.CELERY_TASK_FAILURES)


@task_retry.connect
def _on_task_retry(request=None, reason=None, sender=None, **_kwargs):
    if sender is None or request is None or not request.id:
        return
    record_task_retrying(
        task_name=sender.name,
        task_id=request.id,
        retry_count=getattr(request, "retries", 0) or 0,
        max_retries=getattr(sender, "max_retries", 0) or 0,
        exception=reason
        if isinstance(reason, BaseException)
        else RuntimeError(str(reason)),
    )


@task_postrun.connect
def _on_task_postrun(*_, **__):
    clear_context()


@task_failure.connect
def persist_terminal_failure(
    sender=None,
    task_id=None,
    exception=None,
    **_kwargs,
):
    if sender is None or not task_id or exception is None:
        return
    max_retries = getattr(sender, "max_retries", 0) or 0
    current_retries = getattr(getattr(sender, "request", None), "retries", 0) or 0
    if current_retries < max_retries:
        return
    record_task_failed(
        task_name=sender.name,
        task_id=task_id,
        retry_count=current_retries,
        max_retries=max_retries,
        exception=exception,
    )


@task_postrun.connect
def persist_task_success(sender=None, task_id=None, state=None, **_kwargs):
    if sender is None or not task_id:
        return
    if state == "SUCCESS":
        record_task_succeeded(task_name=sender.name, task_id=task_id)


@celery_app.task
def hello_world():
    """Minimal task used to verify that the Celery worker is wired up."""
    return {"message": "hello world", "status": "ok"}


@celery_app.task(name="app.tasks.celery_app.record_dead_letter")
def record_dead_letter(payload: dict):
    """Persist terminal task failure payload to a dead-letter queue."""
    logger.error("Dead-letter task received: %s", redact_log_data(payload))
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
    logger.error("Routing task failure to dead-letter queue: %s", redact_log_data(payload))
    celery_app.send_task(
        "app.tasks.celery_app.record_dead_letter",
        kwargs={"payload": payload},
        queue="dead_letter",
    )
