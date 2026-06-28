"""Shared test fixtures, safe test defaults, and SQLite compatibility shims."""

from __future__ import annotations

import hashlib
import os
import signal
from types import FrameType, SimpleNamespace

import pytest
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

from tests.helpers.fake_redis import FakeRedisRateLimiter

_TEST_TIMEOUT_SECONDS = int(os.getenv("ADC_PYTEST_TIMEOUT_SECONDS", "60"))

_TEST_ENV_DEFAULTS = {
    "APP_ENV": "test",
}


for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)


def _handle_test_timeout(signum: int, frame: FrameType | None) -> None:
    raise TimeoutError(f"pytest test exceeded {_TEST_TIMEOUT_SECONDS} seconds")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    """Bound each test item so one hang cannot stall the full backend suite."""

    if _TEST_TIMEOUT_SECONDS <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_test_timeout)
    signal.alarm(_TEST_TIMEOUT_SECONDS)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


# Register SQLite type compilers so that Postgres-specific column types
# used in the production models can be created in an in-memory SQLite DB.


@compiles(PG_JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "CHAR(32)"


@pytest.fixture(autouse=True)
def _fake_weasyprint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic PDF bytes for tests without native WeasyPrint deps.

    The fake bytes embed a fingerprint of the input HTML so tests can assert
    *which* template a caller went through without needing the real
    WeasyPrint native libraries.
    """

    class _FakeHTML:
        def __init__(self, string: str, base_url: str | None = None):
            self.string = string
            self.base_url = base_url

        def write_pdf(self) -> bytes:
            # Include a short, stable fingerprint of the HTML so tests can
            # uniquely identify which template was rendered.
            digest = hashlib.sha256(self.string.encode("utf-8")).hexdigest()[:16]
            return b"%PDF-1.4\nfake-weasyprint:" + digest.encode("ascii")

    monkeypatch.setitem(__import__("sys").modules, "weasyprint", SimpleNamespace(HTML=_FakeHTML))


@pytest.fixture(autouse=True)
def _fake_rate_limit_redis() -> None:
    from app.api import routes_driver_auth
    from app.services import rate_limit_service

    fake_redis = FakeRedisRateLimiter()
    routes_driver_auth._redis_client = fake_redis
    routes_driver_auth._rate_limit_script_sha = None
    rate_limit_service._redis_client = fake_redis
    rate_limit_service._rate_limit_script_sha = None
    yield
    routes_driver_auth._redis_client = None
    routes_driver_auth._rate_limit_script_sha = None
    rate_limit_service._redis_client = None
    rate_limit_service._rate_limit_script_sha = None
