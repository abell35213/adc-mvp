"""Logging configuration and request-scoped correlation helpers."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
_org_id_ctx: ContextVar[str | None] = ContextVar("org_id", default=None)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON with correlation context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "user_id": get_user_id(),
            "org_id": get_org_id(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        for key in ("path", "method", "status_code", "metric", "value"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        return json.dumps(payload, default=str)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate request-scoped logging fields and return a request id header."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        set_request_id(request_id)
        set_log_context(
            user_id=_optional_header(request.headers.get("x-user-id")),
            org_id=_optional_header(request.headers.get("x-org-id")),
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        clear_log_context()
        return response


def _optional_header(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def setup_logging(level: str = "INFO") -> None:
    """Configure JSON logging for the app and workers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def set_request_id(request_id: str | None) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_log_context(user_id: str | None = None, org_id: str | None = None) -> None:
    _user_id_ctx.set(user_id)
    _org_id_ctx.set(org_id)


def clear_log_context() -> None:
    _request_id_ctx.set(None)
    _user_id_ctx.set(None)
    _org_id_ctx.set(None)


def get_user_id() -> str | None:
    return _user_id_ctx.get()


def get_org_id() -> str | None:
    return _org_id_ctx.get()


@contextmanager
def log_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    org_id: str | None = None,
):
    """Temporarily set request/user/org context fields."""
    prior_request_id = get_request_id()
    prior_user_id = get_user_id()
    prior_org_id = get_org_id()

    if request_id is not None:
        set_request_id(request_id)
    if user_id is not None or org_id is not None:
        set_log_context(user_id=user_id, org_id=org_id)

    try:
        yield
    finally:
        _request_id_ctx.set(prior_request_id)
        _user_id_ctx.set(prior_user_id)
        _org_id_ctx.set(prior_org_id)
