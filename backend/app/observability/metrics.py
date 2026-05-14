"""Unified metrics API with pluggable backends."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock
from typing import Any, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


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




class _CounterLike(Protocol):
    def inc(self, amount: int) -> None: ...


class _HistogramLike(Protocol):
    def observe(self, value: float) -> None: ...


class _OtelCounterLike(Protocol):
    def add(self, amount: int) -> None: ...


class _OtelHistogramLike(Protocol):
    def record(self, value: int) -> None: ...


class _InMemoryExporter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)

    def increment(self, metric: str, value: int) -> int:
        with self._lock:
            self._counters[metric] += value
            return self._counters[metric]

    def timing(self, metric: str, elapsed_ms: int) -> None:
        logger.debug("in-memory timing", extra={"metric": metric, "value": elapsed_ms})


class _PrometheusExporter:
    def __init__(self) -> None:
        try:
            from prometheus_client import Counter, Histogram  # type: ignore
        except Exception:  # pragma: no cover - optional dependency path
            self._fallback = _InMemoryExporter()
            self._available = False
            return

        self._counter_cls = Counter
        self._histogram_cls = Histogram
        self._counters: dict[str, _CounterLike] = {}
        self._histograms: dict[str, _HistogramLike] = {}
        self._available = True

    def increment(self, metric: str, value: int) -> int:
        if not self._available:
            return self._fallback.increment(metric, value)

        normalized = metric.replace(".", "_")
        counter = self._counters.get(normalized)
        if counter is None:
            counter = self._counter_cls(normalized, f"Counter for {metric}")
            self._counters[normalized] = counter
        counter.inc(value)
        return value

    def timing(self, metric: str, elapsed_ms: int) -> None:
        if not self._available:
            self._fallback.timing(metric, elapsed_ms)
            return
        normalized = metric.replace(".", "_")
        histogram = self._histograms.get(normalized)
        if histogram is None:
            histogram = self._histogram_cls(normalized, f"Timing for {metric}")
            self._histograms[normalized] = histogram
        histogram.observe(elapsed_ms / 1000)


class _OtelExporter:
    def __init__(self) -> None:
        try:
            from opentelemetry import metrics as otel_metrics  # type: ignore
        except Exception:  # pragma: no cover - optional dependency path
            self._fallback = _InMemoryExporter()
            self._available = False
            return

        self._meter = otel_metrics.get_meter("adc_mvp")
        self._counters: dict[str, _OtelCounterLike] = {}
        self._histograms: dict[str, _OtelHistogramLike] = {}
        self._available = True

    def increment(self, metric: str, value: int) -> int:
        if not self._available:
            return self._fallback.increment(metric, value)
        counter = self._counters.get(metric)
        if counter is None:
            counter = self._meter.create_counter(metric)
            self._counters[metric] = counter
        counter.add(value)
        return value

    def timing(self, metric: str, elapsed_ms: int) -> None:
        if not self._available:
            self._fallback.timing(metric, elapsed_ms)
            return
        histogram = self._histograms.get(metric)
        if histogram is None:
            histogram = self._meter.create_histogram(metric)
            self._histograms[metric] = histogram
        histogram.record(elapsed_ms)


class _DatadogExporter:
    def __init__(self) -> None:
        try:
            from datadog import statsd  # type: ignore
        except Exception:  # pragma: no cover - optional dependency path
            self._fallback = _InMemoryExporter()
            self._available = False
            return

        self._statsd = statsd
        self._available = True

    def increment(self, metric: str, value: int) -> int:
        if not self._available:
            return self._fallback.increment(metric, value)
        self._statsd.increment(metric, value)
        return value

    def timing(self, metric: str, elapsed_ms: int) -> None:
        if not self._available:
            self._fallback.timing(metric, elapsed_ms)
            return
        self._statsd.timing(metric, elapsed_ms)


def _build_exporter() -> Any:
    backend = settings.METRICS_BACKEND.strip().lower()
    if backend == "prometheus":
        return _PrometheusExporter()
    if backend in {"opentelemetry", "otel"}:
        return _OtelExporter()
    if backend == "datadog":
        return _DatadogExporter()
    return _InMemoryExporter()


_exporter = _build_exporter()


def increment(metric: str, value: int = 1) -> int:
    current_value = _exporter.increment(metric, value)
    logger.info("metric increment", extra={"metric": metric, "value": current_value})
    return current_value


@contextmanager
def timed(metric: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        duration_metric = f"{metric}.duration_ms"
        _exporter.timing(duration_metric, elapsed_ms)
        logger.info("metric timing", extra={"metric": duration_metric, "value": elapsed_ms})
