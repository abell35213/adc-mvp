"""Shared test fixtures and SQLite compatibility shims."""

import hashlib
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles


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
