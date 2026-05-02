"""Generic ODBC connector for TMS ingestion (Phase 2).

This module is intentionally thin and pluggable:

* ``ConnectionFactory`` is a ``Protocol`` returning a DB-API-2.0 connection.
  In production the default factory wraps :func:`pyodbc.connect`; tests
  inject a SQLite-backed fake so the connector can be exercised without
  any ODBC driver installed.
* :func:`assert_select_only` enforces the plan's read-only contract: only
  ``SELECT`` (or ``WITH … SELECT``) statements may flow through the
  connector. Anything else raises :class:`NonSelectStatementError` *before*
  it ever reaches the remote database.
* :func:`run_field_map` executes a per-entity field map and returns rows
  shaped as ``{target_field: transformed_value}`` — the unit the
  :mod:`tms_sync_service` upserts on.
* :func:`apply_transform` implements the four transforms enumerated in the
  plan: ``none``, ``date``, ``upper``, ``json_extract:<path>``.

By design this module has **no** ORM or model imports — it is a pure
adapter, which keeps it trivial to unit test.
"""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator, Protocol, Sequence

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Read-only enforcement
# ─────────────────────────────────────────────────────────────────────────────

# Strip block + line comments before classifying so ``/* INSERT */ SELECT …``
# isn't misclassified.
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_LEADING_RE = re.compile(r"^\s*([A-Za-z]+)")

# Per the plan: "the connector wraps every cursor with READ ONLY and rejects
# non-SELECT statements." Common-Table-Expression queries that resolve to a
# SELECT are explicitly allowed; everything else (DML/DDL/DCL) is rejected.
_ALLOWED_VERBS = frozenset({"select", "with"})


class NonSelectStatementError(ValueError):
    """Raised when a non-SELECT statement is submitted to the ODBC connector."""


def _strip_comments(sql: str) -> str:
    """Remove SQL comments without altering semantically meaningful tokens."""
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", sql))


def assert_select_only(sql: str) -> None:
    """Raise :class:`NonSelectStatementError` unless ``sql`` is a single SELECT.

    * Comments are stripped before classification.
    * Multiple statements (``;``-separated, ignoring trailing whitespace) are
      rejected to prevent statement-stacking attacks like ``SELECT 1;
      DROP TABLE x``.
    * Only ``SELECT`` and ``WITH`` (CTE → SELECT) are permitted.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise NonSelectStatementError("SQL must be a non-empty string")

    stripped = _strip_comments(sql).strip().rstrip(";").strip()
    if not stripped:
        raise NonSelectStatementError("SQL is empty after stripping comments")

    # Reject statement stacking (any inner ``;`` after stripping the trailing one).
    if ";" in stripped:
        raise NonSelectStatementError(
            "Multiple statements are not allowed in TMS queries"
        )

    match = _LEADING_RE.match(stripped)
    if match is None:
        raise NonSelectStatementError("Could not classify SQL leading verb")
    verb = match.group(1).lower()
    if verb not in _ALLOWED_VERBS:
        raise NonSelectStatementError(
            f"Only SELECT statements are allowed; got {verb.upper()!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Transforms
# ─────────────────────────────────────────────────────────────────────────────

_JSON_EXTRACT_PREFIX = "json_extract:"


class UnknownTransformError(ValueError):
    """Raised when a field map references an unknown ``transform`` value."""


def apply_transform(value: Any, transform: str) -> Any:
    """Apply one of the plan's enumerated transforms to a raw cell value.

    Supported:

    * ``none`` (or empty/None) — pass-through.
    * ``date`` — parse strings as ISO-8601 dates; pass through datetimes/dates.
    * ``upper`` — uppercase strings; non-strings are returned unchanged.
    * ``json_extract:<path>`` — parse the value as JSON (if it's a string)
      and walk a dot-separated path. Returns ``None`` if any segment is
      missing rather than raising — this matches the plan's "best-effort
      ingest" intent.
    """
    if value is None:
        return None
    t = (transform or "none").strip().lower()
    if t == "none":
        return value
    if t == "date":
        if isinstance(value, (datetime, date)):
            return value
        if not isinstance(value, str):
            raise UnknownTransformError(
                f"date transform requires str/date input, got {type(value).__name__}"
            )
        return _parse_date(value)
    if t == "upper":
        return value.upper() if isinstance(value, str) else value
    if t.startswith(_JSON_EXTRACT_PREFIX):
        path = t[len(_JSON_EXTRACT_PREFIX):].strip()
        return _json_extract(value, path)
    raise UnknownTransformError(f"Unknown transform: {transform!r}")


def _parse_date(value: str) -> datetime:
    """Parse an ISO-8601 date or datetime string."""
    text = value.strip()
    # Allow both 'YYYY-MM-DD' and full ISO-8601 with optional Z suffix.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise UnknownTransformError(f"date transform: not ISO-8601: {value!r}") from exc


def _json_extract(value: Any, path: str) -> Any:
    """Walk ``path`` (dot-separated keys) on a JSON-or-dict value."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    current: Any = value
    for segment in (s for s in path.split(".") if s):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return None
    return current


# ─────────────────────────────────────────────────────────────────────────────
# Connection plumbing
# ─────────────────────────────────────────────────────────────────────────────


class ConnectionFactory(Protocol):
    """A callable returning a DB-API-2.0 connection."""

    def __call__(self) -> Any:  # pragma: no cover - structural
        ...


# Default timeouts per the plan: "10 s connect, 30 s query".
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10
DEFAULT_QUERY_TIMEOUT_SECONDS = 30


def make_pyodbc_factory(
    connection_string: str,
    *,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    query_timeout: int = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> ConnectionFactory:
    """Return a factory that opens a real pyodbc connection on demand.

    ``pyodbc`` is imported lazily so this module can be used in tests and
    deployments that don't ship the native ODBC driver. The connection is
    configured ``readonly=True`` as an additional belt-and-braces layer on
    top of :func:`assert_select_only`.
    """

    def _factory() -> Any:
        import pyodbc  # noqa: PLC0415  - lazy import; optional dependency

        conn = pyodbc.connect(
            connection_string,
            timeout=connect_timeout,
            readonly=True,
        )
        conn.timeout = query_timeout
        return conn

    return _factory


@contextmanager
def open_connection(factory: ConnectionFactory) -> Iterator[Any]:
    """Open + close a connection from ``factory`` with try/finally semantics."""
    conn = factory()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            logger.debug("TMS connection close raised; ignoring", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# Field-map execution
# ─────────────────────────────────────────────────────────────────────────────


class FieldMapEntry:
    """A row of ``tms_field_maps``, lifted to a plain dataclass-like object.

    Using a small adapter class (rather than depending on the SQLAlchemy ORM
    type directly) keeps :mod:`tms_odbc_connector` free of ORM imports and
    therefore trivially mockable in tests.
    """

    __slots__ = (
        "source_table",
        "source_column",
        "target_field",
        "transform",
        "is_key",
    )

    def __init__(
        self,
        *,
        source_table: str,
        source_column: str,
        target_field: str,
        transform: str = "none",
        is_key: bool = False,
    ):
        self.source_table = source_table
        self.source_column = source_column
        self.target_field = target_field
        self.transform = transform or "none"
        self.is_key = bool(is_key)


def _quote_ident(name: str) -> str:
    """Conservatively double-quote an identifier (all SQL dialects we accept).

    Field maps come from operator-controlled rows so this is defense in
    depth: we require identifiers to match a strict pattern and re-escape
    any embedded quote characters.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def build_select_for_entries(entries: Sequence[FieldMapEntry]) -> str:
    """Compose a single ``SELECT`` from a per-entity batch of field maps.

    All entries must share the same ``source_table``. Columns are aliased to
    their ``target_field`` so the cursor returns ready-to-upsert dicts.
    """
    if not entries:
        raise ValueError("entries must be non-empty")
    tables = {e.source_table for e in entries}
    if len(tables) != 1:
        raise ValueError(
            f"All field-map entries must share a source_table; got {tables!r}"
        )
    table = next(iter(tables))
    cols = ", ".join(
        f"{_quote_ident(e.source_column)} AS {_quote_ident(e.target_field)}"
        for e in entries
    )
    return f"SELECT {cols} FROM {_quote_ident(table)}"


def run_field_map(
    factory: ConnectionFactory,
    *,
    entries: Sequence[FieldMapEntry],
) -> list[dict[str, Any]]:
    """Run a single-table field-map and return a list of transformed rows.

    The composed SQL is asserted SELECT-only (twice — once on the composed
    string, and the connector itself never accepts free-form SQL from the
    caller). Each cell is then run through :func:`apply_transform` per the
    matching entry's ``transform``.
    """
    sql = build_select_for_entries(entries)
    assert_select_only(sql)

    target_to_transform = {e.target_field: e.transform for e in entries}

    with open_connection(factory) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            description = cursor.description or []
            column_names = [d[0] for d in description]
            raw_rows = cursor.fetchall()
        finally:
            try:
                cursor.close()
            except Exception:  # noqa: BLE001
                logger.debug("TMS cursor close raised; ignoring", exc_info=True)

    out: list[dict[str, Any]] = []
    for raw in raw_rows:
        row_dict: dict[str, Any] = {}
        for idx, name in enumerate(column_names):
            transform = target_to_transform.get(name, "none")
            row_dict[name] = apply_transform(raw[idx], transform)
        out.append(row_dict)
    return out
