"""Shared test fixtures and SQLite compatibility shims."""

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID


# Register SQLite type compilers so that Postgres-specific column types
# used in the production models can be created in an in-memory SQLite DB.

@compiles(PG_JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "CHAR(32)"
