"""Shared test fixtures and SQLite compatibility shims."""

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
    """Provide deterministic PDF bytes for tests without native WeasyPrint deps."""

    class _FakeHTML:
        def __init__(self, string: str):
            self.string = string

        def write_pdf(self) -> bytes:
            return b"%PDF-1.4\nunit-test-pdf"

    monkeypatch.setitem(__import__("sys").modules, "weasyprint", SimpleNamespace(HTML=_FakeHTML))
