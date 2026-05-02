"""Tests for ``driver_unit_history`` repo + TMS sync wiring.

Covers:

* ``upsert_from_tms`` is idempotent on ``(org_id, external_id)``.
* Confidence classification rules (HIGH / MEDIUM / LOW).
* The ``derive_from_assignments`` fallback marks rows LOW.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, DriverUnitHistory, Org


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionMaker = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org(db_session):
    org = Org(name="Acme", sms_enabled=False, voice_enabled=False)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


def test_upsert_classifies_high_when_window_and_unit_id(db_session, org):
    from app.db.repo.driver_unit_history import upsert_from_tms

    import uuid as _uuid
    driver_id = _uuid.uuid4()
    row, created = upsert_from_tms(
        db_session,
        org_id=org.id,
        external_id="tms-row-1",
        fields={
            "driver_id": driver_id,
            "vin": "1FUJGLDV6CSBR1234",
            "started_at_utc": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "ended_at_utc": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "unit_kind": "tractor",
        },
    )
    assert created is True
    assert row.confidence == "high"
    assert row.source == "tms"


def test_upsert_classifies_medium_when_open_ended(db_session, org):
    from app.db.repo.driver_unit_history import upsert_from_tms

    import uuid as _uuid
    row, _ = upsert_from_tms(
        db_session,
        org_id=org.id,
        external_id="tms-row-2",
        fields={
            "driver_id": _uuid.uuid4(),
            "vin": "1FUJGLDV6CSBR9999",
            "started_at_utc": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "unit_kind": "tractor",
        },
    )
    assert row.confidence == "medium"


def test_upsert_classifies_low_when_driver_unresolved(db_session, org):
    from app.db.repo.driver_unit_history import upsert_from_tms

    row, _ = upsert_from_tms(
        db_session,
        org_id=org.id,
        external_id="tms-row-3",
        fields={
            "adc_driver_id": "raw-tms-id",
            "vin": "VIN1",
            "started_at_utc": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "ended_at_utc": datetime(2026, 6, 1, tzinfo=timezone.utc),
            "unit_kind": "tractor",
        },
    )
    assert row.confidence == "low"
    assert row.confidence_reason == "driver_unresolved"


def test_upsert_is_idempotent(db_session, org):
    from app.db.repo.driver_unit_history import upsert_from_tms

    import uuid as _uuid
    driver_id = _uuid.uuid4()
    fields = {
        "driver_id": driver_id,
        "vin": "VIN1",
        "started_at_utc": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "ended_at_utc": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "unit_kind": "tractor",
    }
    row1, created1 = upsert_from_tms(
        db_session, org_id=org.id, external_id="tms-row-X", fields=fields
    )
    assert created1 is True
    row2, created2 = upsert_from_tms(
        db_session,
        org_id=org.id,
        external_id="tms-row-X",
        fields={**fields, "license_plate": "ABC1234"},
    )
    assert created2 is False
    assert row2.id == row1.id
    assert row2.license_plate == "ABC1234"
    # No duplicate row was inserted.
    count = (
        db_session.query(DriverUnitHistory)
        .filter(
            DriverUnitHistory.org_id == org.id,
            DriverUnitHistory.external_id == "tms-row-X",
        )
        .count()
    )
    assert count == 1


def test_derive_from_assignments_returns_low_confidence_rows(db_session, org):
    from app.db.models import DriverVehicleAssignment
    from app.db.repo.driver_unit_history import derive_from_assignments

    import uuid as _uuid
    driver_id = _uuid.uuid4()
    db_session.add(
        DriverVehicleAssignment(
            org_id=org.id,
            driver_id=driver_id,
            adc_vehicle_id="TRUCK-007",
            assigned_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source="manual",
        )
    )
    db_session.commit()

    rows = derive_from_assignments(db_session, org_id=org.id, driver_id=driver_id)
    assert len(rows) == 1
    assert rows[0].confidence == "low"
    assert rows[0].source == "derived_from_assignment"
    assert rows[0].adc_vehicle_id == "TRUCK-007"
