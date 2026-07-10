from __future__ import annotations

import ast
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

    result = subprocess.run(
        ["alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        check=False,
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
    finally:
        engine.dispose()


def _literal_first_arg(call: ast.Call) -> str | None:
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _walk_calls(path: Path) -> list[tuple[str, str]]:
    tree = ast.parse(path.read_text())
    calls: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            calls.append((func.attr, _literal_first_arg(node) or ""))
    return calls


def test_archived_migration_lineage_documents_known_missing_tables() -> None:
    created: dict[str, str] = {}
    referenced: dict[str, list[str]] = {}
    for path in sorted(ARCHIVE.glob("*.py")):
        revision = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)", path.read_text())
        revision_id = revision.group(1) if revision else path.stem
        text = path.read_text()
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
