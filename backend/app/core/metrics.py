"""Lightweight in-process metrics helpers for key ADC flows."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)

_counter_lock = Lock()
_counters: dict[str, int] = defaultdict(int)


class MetricNames:
    AUTH_LOGIN_ATTEMPTS = "auth.login.attempts"
    AUTH_LOGIN_FAILURES = "auth.login.failures"
    AUTH_REGISTER_ATTEMPTS = "auth.register.attempts"
    AUTH_REGISTER_FAILURES = "auth.register.failures"

    INCIDENT_CREATE_ATTEMPTS = "incidents.create.attempts"
    INCIDENT_CREATE_FAILURES = "incidents.create.failures"

    EXPORT_REQUEST_ATTEMPTS = "exports.request.attempts"
    EXPORT_REQUEST_FAILURES = "exports.request.failures"
    EXPORT_DOWNLOAD_ATTEMPTS = "exports.download.attempts"
    EXPORT_DOWNLOAD_FAILURES = "exports.download.failures"

    TWILIO_WEBHOOK_ATTEMPTS = "twilio.webhook.attempts"
    TWILIO_WEBHOOK_FAILURES = "twilio.webhook.failures"
    TWILIO_SEND_SMS_FAILURES = "twilio.send_sms.failures"
    TWILIO_PLACE_CALL_FAILURES = "twilio.place_call.failures"

    CELERY_TASK_STARTED = "celery.task.started"
    CELERY_TASK_FAILURES = "celery.task.failures"


def increment(metric: str, value: int = 1) -> int:
    """Increment metric counter and emit a structured log point."""
    with _counter_lock:
        _counters[metric] += value
        current_value = _counters[metric]

    logger.info("metric increment", extra={"metric": metric, "value": current_value})
    return current_value


@contextmanager
def timed(metric: str):
    """Measure duration for a block and emit a timing log line."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "metric timing",
            extra={"metric": f"{metric}.duration_ms", "value": elapsed_ms},
        )
