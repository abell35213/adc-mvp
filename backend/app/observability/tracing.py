"""Tracing and correlation-context helpers shared by API and workers."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Mapping, MutableMapping
from uuid import uuid4

CORRELATION_ID_HEADER = "x-request-id"
USER_ID_HEADER = "x-user-id"
ORG_ID_HEADER = "x-org-id"

_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
_org_id_ctx: ContextVar[str | None] = ContextVar("org_id", default=None)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def new_correlation_id() -> str:
    return str(uuid4())


def set_correlation_id(correlation_id: str | None) -> None:
    _correlation_id_ctx.set(_clean_optional(correlation_id))


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


def set_actor_context(*, user_id: str | None = None, org_id: str | None = None) -> None:
    _user_id_ctx.set(_clean_optional(user_id))
    _org_id_ctx.set(_clean_optional(org_id))


def get_user_id() -> str | None:
    return _user_id_ctx.get()


def get_org_id() -> str | None:
    return _org_id_ctx.get()


def clear_context() -> None:
    _correlation_id_ctx.set(None)
    _user_id_ctx.set(None)
    _org_id_ctx.set(None)


def extract_correlation_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    source = headers or {}
    correlation_id = _clean_optional(source.get(CORRELATION_ID_HEADER)) or new_correlation_id()
    return {
        CORRELATION_ID_HEADER: correlation_id,
        USER_ID_HEADER: _clean_optional(source.get(USER_ID_HEADER)) or "",
        ORG_ID_HEADER: _clean_optional(source.get(ORG_ID_HEADER)) or "",
    }


def inject_correlation_headers(headers: MutableMapping[str, str] | None = None) -> dict[str, str]:
    target = dict(headers or {})
    target.setdefault(CORRELATION_ID_HEADER, get_correlation_id() or new_correlation_id())

    user_id = get_user_id()
    org_id = get_org_id()
    if user_id:
        target.setdefault(USER_ID_HEADER, user_id)
    if org_id:
        target.setdefault(ORG_ID_HEADER, org_id)

    return target


@contextmanager
def correlation_context(
    *,
    correlation_id: str | None = None,
    user_id: str | None = None,
    org_id: str | None = None,
) -> Iterator[None]:
    previous = (get_correlation_id(), get_user_id(), get_org_id())

    if correlation_id is not None:
        set_correlation_id(correlation_id)
    if user_id is not None or org_id is not None:
        set_actor_context(user_id=user_id, org_id=org_id)

    try:
        yield
    finally:
        set_correlation_id(previous[0])
        set_actor_context(user_id=previous[1], org_id=previous[2])


# Backwards-compatible aliases for existing imports.
set_request_id = set_correlation_id
get_request_id = get_correlation_id
set_log_context = set_actor_context
clear_log_context = clear_context
log_context = correlation_context
