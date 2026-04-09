"""Alerting and exception-capture integrations."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.observability.redaction import redact_log_data

logger = logging.getLogger(__name__)
_sentry_ready = False


def init_sentry(*, service: str) -> None:
    """Initialize Sentry if configured."""
    global _sentry_ready

    if _sentry_ready:
        return

    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        logger.info("Sentry disabled; no DSN configured", extra={"alert": "sentry.disabled"})
        return

    try:
        import sentry_sdk
    except Exception:
        logger.warning(
            "Sentry SDK unavailable; add sentry-sdk dependency",
            extra={"alert": "sentry.unavailable"},
        )
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.APP_ENV,
        release=settings.RELEASE,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )
    sentry_sdk.set_tag("service", service)
    sentry_sdk.set_tag("environment", settings.APP_ENV)
    sentry_sdk.set_tag("release", settings.RELEASE)

    _sentry_ready = True


def capture_exception(exc: Exception, *, context: dict[str, Any] | None = None) -> None:
    logger.exception("Unhandled exception", exc_info=exc, extra=redact_log_data({"alert": "exception", "context": context or {}}))
    if not _sentry_ready:
        return

    import sentry_sdk

    with sentry_sdk.push_scope() as scope:
        for key, value in redact_log_data(context or {}).items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(exc)


def capture_message(message: str, *, level: str = "warning", **context: Any) -> None:
    log_level = getattr(logging, level.upper(), logging.WARNING)
    safe_context = redact_log_data(context)
    logger.log(log_level, redact_log_data(message), extra={"alert": "message", "context": safe_context})
    if not _sentry_ready:
        return

    import sentry_sdk

    with sentry_sdk.push_scope() as scope:
        for key, value in safe_context.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_message(redact_log_data(message), level=level)
