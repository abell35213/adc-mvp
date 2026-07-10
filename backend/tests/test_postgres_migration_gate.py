from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect

from app.db.models import Base

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
VERSIONS = BACKEND / "app" / "db" / "migrations" / "versions"
ARCHIVE = BACKEND / "app" / "db" / "migrations" / "archived_broken_history_20260710"


@pytest.mark.skipif(
    not os.getenv("POSTGRES_MIGRATION_DATABASE_URL"), reason="requires PostgreSQL"
)
def test_fresh_postgres_upgrade_head_creates_all_orm_tables() -> None:
    database_url = os.environ["POSTGRES_MIGRATION_DATABASE_URL"]
    env = {**os.environ, "DATABASE_URL": database_url}
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(sa.text("CREATE SCHEMA public"))
            conn.execute(sa.text("GRANT ALL ON SCHEMA public TO CURRENT_USER"))
    finally:
        engine.dispose()

    result = subprocess.run(
        ["alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    engine = sa.create_engine(database_url)
    try:
        inspector = inspect(engine)
        migrated_tables = set(inspector.get_table_names(schema="public")) - {
            "alembic_version"
        }
        orm_tables = set(Base.metadata.tables)
        assert migrated_tables == orm_tables
        for table in orm_tables:
            migrated_columns = {column["name"] for column in inspector.get_columns(table, schema="public")}
            orm_columns = {column.name for column in Base.metadata.tables[table].columns}
            assert migrated_columns == orm_columns
    finally:
        engine.dispose()


def test_archived_migration_lineage_documents_known_missing_tables() -> None:
    created: dict[str, str] = {}
    referenced: dict[str, list[str]] = {}
    for path in sorted(ARCHIVE.glob("*.py")):
        text = path.read_text()
        revision = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)", text)
        revision_id = revision.group(1) if revision else path.stem
        for match in re.finditer(r"op\.create_table\(\s*['\"]([^'\"]+)", text):
            created.setdefault(match.group(1), revision_id)
        for table in Base.metadata.tables:
            if re.search(rf"['\"]{re.escape(table)}['\"]", text):
                referenced.setdefault(table, []).append(revision_id)

    missing = set(Base.metadata.tables) - set(created)
    assert {
        "integration_connections",
        "integration_operations",
        "integration_operation_status_history",
        "evidence_requests",
        "external_mappings",
        "provider_webhook_events",
        "message_operations",
        "org_vehicle_registry",
        "vehicle_import_jobs",
    }.issubset(missing)
    assert "0017" in referenced["message_operations"]


def test_active_migrations_do_not_reference_tables_before_creation() -> None:
    created: set[str] = set()
    orm_tables = set(Base.metadata.tables)
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text()
        for table in orm_tables:
            if re.search(rf"['\"]{re.escape(table)}['\"]", text):
                assert table in created or "Base.metadata.create_all" in text
        created.update(re.findall(r"op\.create_table\(\s*['\"]([^'\"]+)", text))
    if not created:
        assert "Base.metadata.create_all" in "\n".join(
            p.read_text() for p in VERSIONS.glob("*.py")
        )


def test_active_migrations_do_not_explicitly_create_named_enum_then_reuse_it() -> None:
    for path in VERSIONS.glob("*.py"):
        text = path.read_text()
        assert ".create(op.get_bind(), checkfirst=True)" not in text
        assert ".create(bind, checkfirst=True)" not in text
