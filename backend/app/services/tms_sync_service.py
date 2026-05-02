"""TMS sync service — pulls trailer + maintenance rows into the local cache.

Per the Phase-2 plan:

* The packet has a hard 15-minute SLA, so the canonical query never reaches
  out to a TMS at packet time. Instead, this service runs nightly (via
  ``tms_connection.schedule_cron``) **and** on-demand to keep the local
  cache fresh.
* Each :class:`TmsConnection` may have many :class:`TmsFieldMap` rows
  describing how source columns map to ``trailer`` / ``maintenance_record``
  fields. Field maps are grouped by entity, executed as a single
  read-only ``SELECT`` per entity, and upserted by
  ``(org_id, external_id)`` (idempotent re-sync).
* Errors are surfaced via :attr:`TmsConnection.status` /
  :attr:`TmsConnection.last_error` and bubbled up to the caller so the
  Celery task can decide retry policy.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.db.models import TmsConnection, TmsFieldMap
from app.db.repo.dispatch_instructions import (
    upsert_from_tms as upsert_dispatch_instruction,
)
from app.db.repo.driver_unit_history import (
    upsert_from_tms as upsert_driver_unit_history,
)
from app.db.repo.loading_dock_reports import (
    upsert_from_tms as upsert_loading_dock_report,
)
from app.db.repo.maintenance_records import upsert_from_tms as upsert_maintenance
from app.db.repo.trailers import upsert_from_tms as upsert_trailer
from app.db.repo.weigh_station_reports import (
    upsert_from_tms as upsert_weigh_station_report,
)
from app.services.tms_odbc_connector import (
    ConnectionFactory,
    FieldMapEntry,
    make_pyodbc_factory,
    run_field_map,
)

logger = logging.getLogger(__name__)


@dataclass
class EntitySyncResult:
    """Outcome of syncing one entity (trailer/maintenance) for a connection."""

    entity: str
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    error: str | None = None


@dataclass
class ConnectionSyncResult:
    """Outcome of syncing all entities for one TMS connection."""

    tms_connection_id: _uuid.UUID
    started_at_utc: datetime
    finished_at_utc: datetime | None = None
    entity_results: list[EntitySyncResult] = field(default_factory=list)
    error: str | None = None

    @property
    def total_inserted(self) -> int:
        return sum(r.inserted for r in self.entity_results)

    @property
    def total_updated(self) -> int:
        return sum(r.updated for r in self.entity_results)


# ─────────────────────────────────────────────────────────────────────────────
# Secret resolution
# ─────────────────────────────────────────────────────────────────────────────


# Type alias for "given a secret reference, return the connection string".
SecretResolver = Callable[[str], str]


def _default_secret_resolver(ref: str) -> str:
    """Default ODBC-secret resolver.

    * When ``SECRET_PROVIDER=aws_secrets_manager`` we fetch the named secret
      from AWS Secrets Manager directly (the global app-settings JSON blob
      is the wrong place for per-connection DSNs).
    * Otherwise we fall back to ``os.getenv(ref)`` so local dev can wire a
      DSN through an env var.
    """
    import os

    from app.config.settings import settings

    provider = (settings.SECRET_PROVIDER or "env").strip().lower()
    if provider == "aws_secrets_manager":
        import boto3  # noqa: PLC0415 - optional in some test envs

        region = (
            settings.AWS_SECRETS_MANAGER_REGION
            or os.getenv("AWS_REGION")
            or "us-east-1"
        )
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=ref)
        return response.get("SecretString") or ""
    return os.getenv(ref, "")


# ─────────────────────────────────────────────────────────────────────────────
# Sync orchestration
# ─────────────────────────────────────────────────────────────────────────────


def _entries_for_entity(
    field_maps: list[TmsFieldMap], entity: str
) -> list[FieldMapEntry]:
    return [
        FieldMapEntry(
            source_table=fm.source_table,
            source_column=fm.source_column,
            target_field=fm.target_field,
            transform=fm.transform,
            is_key=fm.is_key,
        )
        for fm in field_maps
        if fm.entity == entity
    ]


def _key_value(
    row: dict, entries: list[FieldMapEntry]
) -> str | None:
    """Pick the row's external-id value from the first ``is_key=True`` entry."""
    for e in entries:
        if e.is_key:
            v = row.get(e.target_field)
            return None if v is None else str(v)
    # Fall back to a column literally named 'external_id'.
    v = row.get("external_id")
    return None if v is None else str(v)


def _sync_trailers(
    db: Session,
    *,
    org_id: _uuid.UUID,
    factory: ConnectionFactory,
    entries: list[FieldMapEntry],
) -> EntitySyncResult:
    result = EntitySyncResult(entity="trailer")
    if not entries:
        return result
    try:
        rows = run_field_map(factory, entries=entries)
    except Exception as exc:  # noqa: BLE001 - surface the message
        result.error = f"select_failed: {exc}"
        return result

    for row in rows:
        ext = _key_value(row, entries)
        if not ext:
            result.skipped += 1
            continue
        try:
            _, created = upsert_trailer(
                db, org_id=org_id, external_id=ext, fields=row
            )
            if created:
                result.inserted += 1
            else:
                result.updated += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "Trailer upsert failed for org=%s external_id=%s", org_id, ext
            )
            result.skipped += 1
    return result


def _sync_maintenance(
    db: Session,
    *,
    org_id: _uuid.UUID,
    factory: ConnectionFactory,
    entries: list[FieldMapEntry],
) -> EntitySyncResult:
    result = EntitySyncResult(entity="maintenance_record")
    if not entries:
        return result
    try:
        rows = run_field_map(factory, entries=entries)
    except Exception as exc:  # noqa: BLE001
        result.error = f"select_failed: {exc}"
        return result

    for row in rows:
        ext = _key_value(row, entries)
        if not ext:
            result.skipped += 1
            continue
        try:
            _, created = upsert_maintenance(
                db, org_id=org_id, external_id=ext, fields=row
            )
            if created:
                result.inserted += 1
            else:
                result.updated += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "Maintenance upsert failed for org=%s external_id=%s",
                org_id,
                ext,
            )
            result.skipped += 1
    return result


def _sync_simple_entity(
    db: Session,
    *,
    org_id: _uuid.UUID,
    factory: ConnectionFactory,
    entries: list[FieldMapEntry],
    entity_name: str,
    upsert_fn,
) -> EntitySyncResult:
    """Generic per-entity sync used for the Phase-3 entities.

    Identical shape to :func:`_sync_trailers` / :func:`_sync_maintenance` but
    parameterized on the upsert callable so we don't duplicate the same
    select-then-upsert loop four more times.
    """
    result = EntitySyncResult(entity=entity_name)
    if not entries:
        return result
    try:
        rows = run_field_map(factory, entries=entries)
    except Exception as exc:  # noqa: BLE001
        result.error = f"select_failed: {exc}"
        return result

    for row in rows:
        ext = _key_value(row, entries)
        if not ext:
            result.skipped += 1
            continue
        try:
            _, created = upsert_fn(
                db, org_id=org_id, external_id=ext, fields=row
            )
            if created:
                result.inserted += 1
            else:
                result.updated += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "%s upsert failed for org=%s external_id=%s",
                entity_name,
                org_id,
                ext,
            )
            result.skipped += 1
    return result


def sync_connection(
    db: Session,
    *,
    tms_connection_id: _uuid.UUID,
    factory: ConnectionFactory | None = None,
    secret_resolver: SecretResolver | None = None,
) -> ConnectionSyncResult:
    """Sync a single TMS connection's trailers + maintenance into the cache.

    ``factory`` may be injected by tests/admins to bypass DSN resolution; in
    production it's built from ``odbc_secret_ref`` via ``secret_resolver``
    (default: AWS Secrets Manager or env-var fallback).
    """
    started = datetime.now(timezone.utc)
    conn = (
        db.query(TmsConnection)
        .filter(TmsConnection.id == tms_connection_id)
        .first()
    )
    if conn is None:
        raise LookupError(f"TmsConnection {tms_connection_id} not found")

    result = ConnectionSyncResult(
        tms_connection_id=tms_connection_id, started_at_utc=started
    )

    field_maps: list[TmsFieldMap] = (
        db.query(TmsFieldMap)
        .filter(TmsFieldMap.tms_connection_id == tms_connection_id)
        .all()
    )

    if factory is None:
        resolver = secret_resolver or _default_secret_resolver
        try:
            connection_string = resolver(conn.odbc_secret_ref)
        except Exception as exc:  # noqa: BLE001
            conn.status = "error"
            conn.last_error = f"secret_resolution_failed: {exc}"
            result.finished_at_utc = datetime.now(timezone.utc)
            result.error = conn.last_error
            db.commit()
            return result
        if not connection_string:
            conn.status = "error"
            conn.last_error = "secret_resolution_returned_empty"
            result.finished_at_utc = datetime.now(timezone.utc)
            result.error = conn.last_error
            db.commit()
            return result
        factory = make_pyodbc_factory(connection_string)

    trailer_res = _sync_trailers(
        db,
        org_id=conn.org_id,
        factory=factory,
        entries=_entries_for_entity(field_maps, "trailer"),
    )
    maint_res = _sync_maintenance(
        db,
        org_id=conn.org_id,
        factory=factory,
        entries=_entries_for_entity(field_maps, "maintenance_record"),
    )
    dispatch_res = _sync_simple_entity(
        db,
        org_id=conn.org_id,
        factory=factory,
        entries=_entries_for_entity(field_maps, "dispatch_instruction"),
        entity_name="dispatch_instruction",
        upsert_fn=upsert_dispatch_instruction,
    )
    weigh_res = _sync_simple_entity(
        db,
        org_id=conn.org_id,
        factory=factory,
        entries=_entries_for_entity(field_maps, "weigh_station_report"),
        entity_name="weigh_station_report",
        upsert_fn=upsert_weigh_station_report,
    )
    dock_res = _sync_simple_entity(
        db,
        org_id=conn.org_id,
        factory=factory,
        entries=_entries_for_entity(field_maps, "loading_dock_report"),
        entity_name="loading_dock_report",
        upsert_fn=upsert_loading_dock_report,
    )
    duh_res = _sync_simple_entity(
        db,
        org_id=conn.org_id,
        factory=factory,
        entries=_entries_for_entity(field_maps, "driver_unit_history"),
        entity_name="driver_unit_history",
        upsert_fn=upsert_driver_unit_history,
    )
    result.entity_results = [
        trailer_res,
        maint_res,
        dispatch_res,
        weigh_res,
        dock_res,
        duh_res,
    ]

    finished = datetime.now(timezone.utc)
    result.finished_at_utc = finished

    entity_errors = [r.error for r in result.entity_results if r.error]
    if entity_errors:
        conn.status = "error"
        conn.last_error = "; ".join(entity_errors)
        result.error = conn.last_error
    else:
        conn.status = "active"
        conn.last_error = None
    conn.last_synced_at_utc = finished
    db.commit()

    return result


def sync_org(
    db: Session, *, org_id: _uuid.UUID
) -> list[ConnectionSyncResult]:
    """Sync every active TMS connection for one org."""
    connections = (
        db.query(TmsConnection)
        .filter(
            TmsConnection.org_id == org_id, TmsConnection.status != "disabled"
        )
        .all()
    )
    return [
        sync_connection(db, tms_connection_id=c.id) for c in connections
    ]
