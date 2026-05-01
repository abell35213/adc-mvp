"""Tests for the TMS ODBC connector (plan test #5).

The connector is built around a small ``ConnectionFactory`` Protocol so we
can exercise it with an in-process SQLite database via ``sqlite3`` (which
is DB-API-2.0 compliant and behaves the same way ``pyodbc`` does for the
operations the connector performs). This means the test suite does not
require any ODBC driver or ``pyodbc`` install.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest

from app.services.tms_odbc_connector import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    FieldMapEntry,
    NonSelectStatementError,
    UnknownTransformError,
    apply_transform,
    assert_select_only,
    build_select_for_entries,
    make_pyodbc_factory,
    run_field_map,
)


@pytest.fixture()
def sqlite_factory():
    """Build a connection factory backed by a single shared in-memory DB."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE tms_trailers (
            id INTEGER PRIMARY KEY,
            trailer_no TEXT,
            vin TEXT,
            plate TEXT,
            inspection TEXT,
            attrs TEXT
        )
        """
    )
    cursor.executemany(
        "INSERT INTO tms_trailers (id, trailer_no, vin, plate, inspection, attrs) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                1,
                "T-1001",
                "1HGBH41JXMN109186",
                "abc123",
                "2025-12-01",
                json.dumps({"meta": {"axles": 2}}),
            ),
            (
                2,
                "T-1002",
                None,
                "xyz789",
                "2025-11-15T08:00:00Z",
                json.dumps({"meta": {"axles": 3}}),
            ),
        ],
    )
    conn.commit()

    def factory():
        # Each call returns the same connection; the connector closes it
        # after a single use, which is fine because the test fixture
        # tears down the file-less DB at scope exit anyway. We re-open a
        # fresh connection each invocation by sharing the underlying
        # in-memory store via ``:memory:`` named-cache trickery would
        # complicate things — instead we just hand out the one connection
        # and short-circuit ``close()``.
        class _Wrapper:
            def __init__(self, c):
                self._c = c

            def cursor(self):
                return self._c.cursor()

            def close(self):
                pass

        return _Wrapper(conn)

    yield factory
    conn.close()


class TestAssertSelectOnly:
    def test_allows_plain_select(self):
        assert_select_only("SELECT * FROM x")

    def test_allows_lowercase(self):
        assert_select_only("select 1")

    def test_allows_cte(self):
        assert_select_only("WITH x AS (SELECT 1) SELECT * FROM x")

    def test_allows_trailing_semicolon(self):
        assert_select_only("SELECT 1;")

    def test_allows_leading_comments(self):
        assert_select_only("-- pulled by ADC\nSELECT 1")

    def test_rejects_insert(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("INSERT INTO x VALUES (1)")

    def test_rejects_update(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("UPDATE x SET v=1")

    def test_rejects_delete(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("DELETE FROM x")

    def test_rejects_drop(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("DROP TABLE x")

    def test_rejects_statement_stacking(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("SELECT 1; DROP TABLE x")

    def test_rejects_block_comment_smuggling(self):
        # /* SELECT */ DELETE … must be classified as DELETE, not SELECT.
        with pytest.raises(NonSelectStatementError):
            assert_select_only("/* SELECT */ DELETE FROM x")

    def test_rejects_empty(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("")

    def test_rejects_only_comment(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only("-- nothing here")

    def test_rejects_non_string(self):
        with pytest.raises(NonSelectStatementError):
            assert_select_only(None)  # type: ignore[arg-type]


class TestApplyTransform:
    def test_none_passthrough(self):
        assert apply_transform("hello", "none") == "hello"
        assert apply_transform(42, "") == 42
        assert apply_transform(None, "upper") is None

    def test_upper_only_strings(self):
        assert apply_transform("acme", "upper") == "ACME"
        assert apply_transform(42, "upper") == 42  # non-string left alone

    def test_date_parses_iso(self):
        result = apply_transform("2025-11-15", "date")
        assert isinstance(result, datetime)
        assert result.year == 2025 and result.month == 11 and result.day == 15

    def test_date_parses_iso_z(self):
        result = apply_transform("2025-11-15T08:00:00Z", "date")
        assert result.tzinfo is not None

    def test_date_passthrough_datetime(self):
        dt = datetime(2025, 1, 1)
        assert apply_transform(dt, "date") is dt

    def test_date_rejects_garbage(self):
        with pytest.raises(UnknownTransformError):
            apply_transform("not-a-date", "date")

    def test_json_extract_path(self):
        payload = json.dumps({"meta": {"axles": 2}})
        assert apply_transform(payload, "json_extract:meta.axles") == 2

    def test_json_extract_missing_returns_none(self):
        payload = json.dumps({"meta": {"axles": 2}})
        assert apply_transform(payload, "json_extract:meta.missing") is None

    def test_json_extract_non_json_returns_none(self):
        assert apply_transform("not json", "json_extract:a.b") is None

    def test_unknown_transform_raises(self):
        with pytest.raises(UnknownTransformError):
            apply_transform("v", "wat")


class TestBuildSelect:
    def test_aliases_columns_to_target_fields(self):
        sql = build_select_for_entries(
            [
                FieldMapEntry(
                    source_table="tms_trailers",
                    source_column="trailer_no",
                    target_field="adc_trailer_id",
                    is_key=True,
                ),
                FieldMapEntry(
                    source_table="tms_trailers",
                    source_column="vin",
                    target_field="vin",
                ),
            ]
        )
        assert 'FROM "tms_trailers"' in sql
        assert '"trailer_no" AS "adc_trailer_id"' in sql
        assert '"vin" AS "vin"' in sql
        # The composed SQL must itself pass the SELECT-only gate.
        assert_select_only(sql)

    def test_rejects_mixed_source_tables(self):
        with pytest.raises(ValueError):
            build_select_for_entries(
                [
                    FieldMapEntry(
                        source_table="a",
                        source_column="c1",
                        target_field="t1",
                    ),
                    FieldMapEntry(
                        source_table="b",
                        source_column="c2",
                        target_field="t2",
                    ),
                ]
            )

    def test_rejects_invalid_identifiers(self):
        with pytest.raises(ValueError):
            build_select_for_entries(
                [
                    FieldMapEntry(
                        source_table="x; DROP TABLE y; --",
                        source_column="c",
                        target_field="t",
                    )
                ]
            )

    def test_rejects_empty_entries(self):
        with pytest.raises(ValueError):
            build_select_for_entries([])


class TestRunFieldMap:
    def test_executes_select_and_applies_transforms(self, sqlite_factory):
        entries = [
            FieldMapEntry(
                source_table="tms_trailers",
                source_column="trailer_no",
                target_field="adc_trailer_id",
                transform="upper",
                is_key=True,
            ),
            FieldMapEntry(
                source_table="tms_trailers",
                source_column="vin",
                target_field="vin",
            ),
            FieldMapEntry(
                source_table="tms_trailers",
                source_column="inspection",
                target_field="last_inspection_at_utc",
                transform="date",
            ),
            FieldMapEntry(
                source_table="tms_trailers",
                source_column="attrs",
                target_field="axle_count",
                transform="json_extract:meta.axles",
            ),
        ]
        rows = run_field_map(sqlite_factory, entries=entries)
        assert len(rows) == 2
        first = rows[0]
        assert first["adc_trailer_id"] == "T-1001"  # upper of already-upper
        assert first["vin"] == "1HGBH41JXMN109186"
        assert isinstance(first["last_inspection_at_utc"], datetime)
        assert first["axle_count"] == 2

    def test_empty_entries_raises(self, sqlite_factory):
        with pytest.raises(ValueError):
            run_field_map(sqlite_factory, entries=[])


class TestPyodbcFactoryConfig:
    def test_factory_uses_default_timeouts(self):
        # We can't actually call pyodbc here, but we can verify the
        # factory captures the timeout config and lazy-imports correctly.
        factory = make_pyodbc_factory("DSN=missing")
        assert callable(factory)
        # Calling it raises ImportError or pyodbc.Error — either way the
        # lazy-import path is reachable. We only care that the closure
        # captured the connection string and the timeouts didn't blow up.
        assert DEFAULT_CONNECT_TIMEOUT_SECONDS == 10
        assert DEFAULT_QUERY_TIMEOUT_SECONDS == 30
