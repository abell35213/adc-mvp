from __future__ import annotations

import os
import re
import subprocess
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect

from app.db.models import Base

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
VERSIONS = BACKEND / "app" / "db" / "migrations" / "versions"
ARCHIVE = BACKEND / "app" / "db" / "migrations" / "archived_broken_history_20260710"
BASELINE = VERSIONS / "0001_mvp_postgresql_baseline.py"


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location("baseline_0001", BASELINE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _active_migration_text() -> str:
    return "\n".join(path.read_text() for path in sorted(VERSIONS.glob("*.py")))


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
        assert len(migrated_tables) == 63
        for table in orm_tables:
            migrated_columns = {
                column["name"] for column in inspector.get_columns(table, schema="public")
            }
            orm_columns = {column.name for column in Base.metadata.tables[table].columns}
            assert migrated_columns == orm_columns

            migrated_pk = inspector.get_pk_constraint(table, schema="public")[
                "constrained_columns"
            ]
            orm_pk = [column.name for column in Base.metadata.tables[table].primary_key.columns]
            assert migrated_pk == orm_pk

            migrated_unique = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table, schema="public")
            }
            orm_unique = {
                tuple(column.name for column in constraint.columns)
                for constraint in Base.metadata.tables[table].constraints
                if isinstance(constraint, sa.UniqueConstraint)
            }
            assert migrated_unique == orm_unique

            migrated_fks = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                    fk["options"].get("ondelete"),
                )
                for fk in inspector.get_foreign_keys(table, schema="public")
            }
            orm_fks = {
                (
                    tuple(column.name for column in constraint.columns),
                    next(iter(constraint.elements)).column.table.name,
                    tuple(element.column.name for element in constraint.elements),
                    constraint.ondelete,
                )
                for constraint in Base.metadata.tables[table].foreign_key_constraints
            }
            assert migrated_fks == orm_fks

        baseline = _load_baseline_module()
        migrated_enums = {
            enum["name"]: tuple(enum["labels"])
            for enum in inspector.get_enums(schema="public")
            if enum["name"] in baseline.ENUMS
        }
        assert migrated_enums == {
            name: tuple(values) for name, values in baseline.ENUMS.items()
        }

        for index in baseline.INDEXES:
            indexes_by_name = {
                ix["name"]: ix
                for ix in inspector.get_indexes(index["table"], schema="public")
            }
            migrated = indexes_by_name.get(index["name"])
            assert migrated is not None
            assert tuple(migrated["column_names"]) == tuple(index["cols"])
            assert bool(migrated.get("unique")) == bool(index["unique"])
        with engine.connect() as conn:
            trigger_exists = conn.scalar(
                sa.text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_trigger t
                        JOIN pg_class c ON c.oid = t.tgrelid
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE t.tgname = 'trg_prevent_audit_events_mutation'
                          AND c.relname = 'audit_events'
                          AND n.nspname = 'public'
                    )
                    """
                )
            )
            function_exists = conn.scalar(
                sa.text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_proc p
                        JOIN pg_namespace n ON n.oid = p.pronamespace
                        WHERE p.proname = 'prevent_audit_events_mutation'
                          AND n.nspname = 'public'
                    )
                    """
                )
            )
        assert trigger_exists
        assert function_exists
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
        if path == BASELINE:
            baseline = _load_baseline_module()
            created.update(table["name"] for table in baseline.TABLES)
        for table in orm_tables:
            if re.search(rf"['\"]{re.escape(table)}['\"]", text):
                assert table in created
        created.update(re.findall(r"op\.create_table\(\s*['\"]([^'\"]+)", text))
    assert created == orm_tables


def test_active_migrations_do_not_use_application_metadata_create_or_drop() -> None:
    text = _active_migration_text()
    assert "Base.metadata.create_all" not in text
    assert "Base.metadata.drop_all" not in text
    assert "from app.db.models import Base" not in text
    assert "import app.db.models" not in text


def test_fixed_baseline_creates_exact_current_orm_table_set() -> None:
    baseline = _load_baseline_module()
    baseline_tables = {table["name"] for table in baseline.TABLES}
    assert len(baseline_tables) == 63
    assert baseline_tables == set(Base.metadata.tables)


def test_active_migrations_do_not_explicitly_create_named_enum_then_reuse_it() -> None:
    for path in VERSIONS.glob("*.py"):
        text = path.read_text()
        assert ".create(op.get_bind(), checkfirst=True)" not in text
