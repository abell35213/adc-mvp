"""Tests for the TMS sync service (plan test #6).

Covers:
* trailer + maintenance upsert from a fake TMS source
* idempotency on re-sync (UPDATE not INSERT)
* per-entity error surfacing onto ``TmsConnection.last_error``
* secret-resolver failure path
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    MaintenanceRecord,
    Org,
    Trailer,
    TmsConnection,
    TmsFieldMap,
)
from app.services.tms_sync_service import sync_connection, sync_org


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org(db_session):
    org = Org(name="Acme")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def tms_conn(db_session, org):
    conn = TmsConnection(
        org_id=org.id,
        name="Mock McLeod",
        vendor_hint="mcleod",
        odbc_secret_ref="adc/tms/acme/mcleod",
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)

    # Trailer field map.
    db_session.add_all(
        [
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="trailer",
                source_table="tms_trailers",
                source_column="trailer_no",
                target_field="adc_trailer_id",
                is_key=True,
            ),
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="trailer",
                source_table="tms_trailers",
                source_column="vin",
                target_field="vin",
            ),
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="trailer",
                source_table="tms_trailers",
                source_column="trailer_no",
                target_field="external_id",
            ),
            # Maintenance field map.
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="maintenance_record",
                source_table="tms_maintenance",
                source_column="ext",
                target_field="external_id",
                is_key=True,
            ),
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="maintenance_record",
                source_table="tms_maintenance",
                source_column="kind",
                target_field="asset_kind",
            ),
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="maintenance_record",
                source_table="tms_maintenance",
                source_column="aid",
                target_field="asset_id",
            ),
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="maintenance_record",
                source_table="tms_maintenance",
                source_column="performed",
                target_field="performed_at_utc",
                transform="date",
            ),
            TmsFieldMap(
                tms_connection_id=conn.id,
                entity="maintenance_record",
                source_table="tms_maintenance",
                source_column="vendor",
                target_field="vendor",
            ),
        ]
    )
    db_session.commit()
    return conn


def _build_factory(initial_trailer_vin: str = "1HGBH41JXMN109186"):
    """Return a factory yielding a SQLite-backed fake TMS database."""
    sqlite_conn = sqlite3.connect(":memory:")
    cur = sqlite_conn.cursor()
    cur.execute(
        "CREATE TABLE tms_trailers (id INT, trailer_no TEXT, vin TEXT)"
    )
    cur.execute(
        "INSERT INTO tms_trailers VALUES (1, 'T-1001', ?)",
        (initial_trailer_vin,),
    )
    cur.execute(
        """
        CREATE TABLE tms_maintenance (
            id INT, ext TEXT, kind TEXT, aid TEXT, performed TEXT, vendor TEXT
        )
        """
    )
    cur.executemany(
        "INSERT INTO tms_maintenance VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "M-1", "tractor", "T-100", "2025-12-01", "JoeShop"),
            (2, "M-2", "trailer", "T-1001", "2025-11-20", "JoeShop"),
        ],
    )
    sqlite_conn.commit()

    class _Wrapper:
        def __init__(self, c):
            self._c = c

        def cursor(self):
            return self._c.cursor()

        def close(self):
            pass

    def factory():
        return _Wrapper(sqlite_conn)

    factory.sqlite_conn = sqlite_conn  # type: ignore[attr-defined]
    return factory


class TestSyncConnection:
    def test_inserts_trailers_and_maintenance(self, db_session, tms_conn):
        factory = _build_factory()
        result = sync_connection(
            db_session, tms_connection_id=tms_conn.id, factory=factory
        )

        assert result.total_inserted == 3  # 1 trailer + 2 maintenance
        assert result.total_updated == 0
        assert result.error is None

        trailers = db_session.query(Trailer).all()
        assert len(trailers) == 1
        assert trailers[0].adc_trailer_id == "T-1001"
        assert trailers[0].vin == "1HGBH41JXMN109186"
        assert trailers[0].source == "tms"
        assert trailers[0].external_id == "T-1001"
        assert trailers[0].synced_at_utc is not None

        records = db_session.query(MaintenanceRecord).all()
        assert len(records) == 2
        kinds = {r.asset_kind for r in records}
        assert kinds == {"tractor", "trailer"}
        assert all(r.source == "tms" for r in records)
        assert all(r.synced_at_utc is not None for r in records)

        # Connection metadata updated.
        db_session.refresh(tms_conn)
        assert tms_conn.status == "active"
        assert tms_conn.last_error is None
        assert tms_conn.last_synced_at_utc is not None

    def test_re_sync_is_idempotent(self, db_session, tms_conn):
        factory = _build_factory()
        sync_connection(
            db_session, tms_connection_id=tms_conn.id, factory=factory
        )
        # Re-run with the same source data.
        factory2 = _build_factory()
        result = sync_connection(
            db_session, tms_connection_id=tms_conn.id, factory=factory2
        )
        assert result.total_inserted == 0
        assert result.total_updated == 3

        # Still exactly one trailer + two maintenance rows.
        assert db_session.query(Trailer).count() == 1
        assert db_session.query(MaintenanceRecord).count() == 2

    def test_re_sync_updates_changed_fields(self, db_session, tms_conn):
        factory = _build_factory(initial_trailer_vin="OLDVIN0000000")
        sync_connection(
            db_session, tms_connection_id=tms_conn.id, factory=factory
        )
        # New TMS export with a corrected VIN.
        factory2 = _build_factory(initial_trailer_vin="NEWVIN9999999")
        sync_connection(
            db_session, tms_connection_id=tms_conn.id, factory=factory2
        )
        trailer = db_session.query(Trailer).one()
        assert trailer.vin == "NEWVIN9999999"

    def test_select_failure_surfaces_on_connection(self, db_session, tms_conn):
        # Factory whose cursor raises immediately.
        class _Boom:
            def cursor(self):
                class _C:
                    def execute(self, *_):
                        raise RuntimeError("connection refused")

                    def close(self):
                        pass

                return _C()

            def close(self):
                pass

        def factory():
            return _Boom()

        result = sync_connection(
            db_session, tms_connection_id=tms_conn.id, factory=factory
        )
        assert result.error is not None
        assert "select_failed" in result.error

        db_session.refresh(tms_conn)
        assert tms_conn.status == "error"
        assert tms_conn.last_error and "select_failed" in tms_conn.last_error

    def test_secret_resolver_failure_surfaces(self, db_session, tms_conn):
        def bad_resolver(_ref: str) -> str:
            raise RuntimeError("AccessDenied")

        result = sync_connection(
            db_session,
            tms_connection_id=tms_conn.id,
            secret_resolver=bad_resolver,
        )
        assert result.error and "secret_resolution_failed" in result.error
        db_session.refresh(tms_conn)
        assert tms_conn.status == "error"

    def test_secret_resolver_returning_empty_is_an_error(
        self, db_session, tms_conn
    ):
        result = sync_connection(
            db_session,
            tms_connection_id=tms_conn.id,
            secret_resolver=lambda _r: "",
        )
        assert result.error == "secret_resolution_returned_empty"
        db_session.refresh(tms_conn)
        assert tms_conn.status == "error"

    def test_unknown_connection_id_raises(self, db_session):
        import uuid

        with pytest.raises(LookupError):
            sync_connection(db_session, tms_connection_id=uuid.uuid4())


class TestSyncOrg:
    def test_runs_each_active_connection(self, db_session, org, tms_conn):
        # Add a disabled second connection — it should be skipped.
        disabled = TmsConnection(
            org_id=org.id,
            name="Disabled",
            vendor_hint="generic",
            odbc_secret_ref="adc/tms/acme/disabled",
            status="disabled",
        )
        db_session.add(disabled)
        db_session.commit()

        factory = _build_factory()
        # Stub sync_connection-style: easiest to monkey-call by passing
        # factory into sync_connection directly via a tiny wrapper.
        from app.services import tms_sync_service as svc

        original = svc.sync_connection

        def wrapper(db, *, tms_connection_id, **_):
            return original(
                db, tms_connection_id=tms_connection_id, factory=factory
            )

        svc.sync_connection = wrapper  # type: ignore[assignment]
        try:
            results = sync_org(db_session, org_id=org.id)
        finally:
            svc.sync_connection = original  # type: ignore[assignment]

        assert len(results) == 1
        assert results[0].tms_connection_id == tms_conn.id


class TestCanonicalQueryReadsCachedData:
    """Phase 2 SQL extension: trailer + maintenance flow into the packet row."""

    def test_packet_row_includes_trailer_and_maintenance(
        self, db_session, org, tms_conn
    ):
        from app.db.models import Driver, Incident, OrgVehicleRegistry
        from app.services.crash_packet_query import fetch_crash_packet_row

        # Seed driver + vehicle for the canonical query joins.
        driver = Driver(
            org_id=org.id, phone_e164="+15551234567", display_name="Pat"
        )
        db_session.add(driver)
        vehicle = OrgVehicleRegistry(org_id=org.id, unit_number="T-100")
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(driver)

        incident = Incident(
            status="accident_occurred",
            adc_vehicle_id="T-100",
            adc_trailer_id="T-1001",
            adc_driver_id=str(driver.driver_id),
            severity="serious",
            org_id=org.id,
        )
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        # Pre-populate the local cache via a sync.
        sync_connection(
            db_session,
            tms_connection_id=tms_conn.id,
            factory=_build_factory(),
        )
        # And bring two maintenance records *inside* the 1-year window even
        # though the seeded ones are dated 2025 (which may already be older
        # than 1 year from "now"). We do this by directly inserting
        # in-window rows for the join check.
        recent = datetime.now(timezone.utc) - timedelta(days=30)
        db_session.add_all(
            [
                MaintenanceRecord(
                    org_id=org.id,
                    asset_kind="tractor",
                    asset_id="T-100",
                    performed_at_utc=recent,
                    vendor="ShopA",
                    summary="Brake check",
                    source="manual",
                ),
                MaintenanceRecord(
                    org_id=org.id,
                    asset_kind="trailer",
                    asset_id="T-1001",
                    performed_at_utc=recent + timedelta(days=1),
                    vendor="ShopB",
                    summary="Tire rotation",
                    source="manual",
                ),
                # Out-of-window record — must NOT appear in packet.
                MaintenanceRecord(
                    org_id=org.id,
                    asset_kind="tractor",
                    asset_id="T-100",
                    performed_at_utc=datetime.now(timezone.utc)
                    - timedelta(days=400),
                    vendor="OldShop",
                    summary="ancient",
                    source="manual",
                ),
            ]
        )
        db_session.commit()

        row = fetch_crash_packet_row(
            db_session, incident_id=incident.incident_id
        )

        assert row.trailer_json is not None
        assert row.trailer_json["adc_trailer_id"] == "T-1001"
        assert row.trailer_json["source"] == "tms"

        # Maintenance: in-window (manual) tractor + trailer rows; the
        # 400-day-old row is excluded.
        summaries = [m["summary"] for m in row.maintenance_json]
        assert "Brake check" in summaries
        assert "Tire rotation" in summaries
        assert "ancient" not in summaries
        # Sorted newest-first.
        timestamps = [m["performed_at_utc"] for m in row.maintenance_json]
        assert timestamps == sorted(timestamps, reverse=True)
