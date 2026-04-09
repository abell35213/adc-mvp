"""Structured logging and request middleware for observability."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.observability.redaction import redact_log_data

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.tracing import (
    CORRELATION_ID_HEADER,
    ORG_ID_HEADER,
    USER_ID_HEADER,
    clear_context,
    extract_correlation_headers,
    get_correlation_id,
    get_org_id,
    get_user_id,
    set_actor_context,
    set_correlation_id,
)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON with correlation context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_data(record.getMessage()),
            "request_id": get_correlation_id(),
            "user_id": get_user_id(),
            "org_id": get_org_id(),
        }

        if record.exc_info:
            payload["exc_info"] = redact_log_data(self.formatException(record.exc_info))

        for key in ("path", "method", "status_code", "metric", "value", "alert"):
            if hasattr(record, key):
                payload[key] = redact_log_data(getattr(record, key), key=key)

        return json.dumps(payload, default=str)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate request-scoped tracing fields and return correlation id headers."""

    async def dispatch(self, request: Request, call_next):
        extracted = extract_correlation_headers(request.headers)
        set_correlation_id(extracted[CORRELATION_ID_HEADER])
        set_actor_context(
            user_id=extracted.get(USER_ID_HEADER) or None,
            org_id=extracted.get(ORG_ID_HEADER) or None,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = extracted[CORRELATION_ID_HEADER]

        clear_context()
        return response


def setup_logging(level: str = "INFO") -> None:
    """Configure JSON logging for API and workers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
