"""Unit tests for the Phase-3 dispatch / weigh / loading dock repos.

Validates:

* Manual create coexists with TMS upsert (manual rows preserved per
  clarifying answer #1).
* TMS upsert is idempotent on ``(org_id, external_id)``.
* Loading dock photo many-to-one linking via
  :attr:`Artifact.loading_dock_report_id`.
* :func:`weigh_station_reports.upsert_from_tms` derives
  ``is_over_legal_limit`` from gross + legal limit when not provided.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Artifact, Base, Org
from app.db.repo import (
    dispatch_instructions as dispatch_repo,
    loading_dock_reports as dock_repo,
    weigh_station_reports as weigh_repo,
)


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
    org = Org(name="Acme", sms_enabled=False, voice_enabled=False)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


class TestDispatchInstructionRepo:
    def test_create_manual_round_trip(self, db_session, org):
        record = dispatch_repo.create_manual(
            db_session,
            org_id=org.id,
            fields={
                "dispatch_id": "DSP-1",
                "load_number": "LD-1",
                "forced_dispatch_flag": True,
                "dispatched_at_utc": datetime(2026, 5, 1, tzinfo=timezone.utc),
            },
        )
        assert record.source == "manual"
        assert record.external_id is None
        assert record.forced_dispatch_flag is True

        fetched = dispatch_repo.get_by_id(
            db_session, org_id=org.id, dispatch_id=record.id
        )
        assert fetched is not None
        assert fetched.dispatch_id == "DSP-1"

    def test_upsert_from_tms_is_idempotent(self, db_session, org):
        a, created_a = dispatch_repo.upsert_from_tms(
            db_session,
            org_id=org.id,
            external_id="ext-1",
            fields={"dispatch_id": "DSP-1", "load_number": "LD-1"},
        )
        assert created_a is True
        b, created_b = dispatch_repo.upsert_from_tms(
            db_session,
            org_id=org.id,
            external_id="ext-1",
            fields={"dispatch_id": "DSP-1", "load_number": "LD-2"},
        )
        assert created_b is False
        assert a.id == b.id
        assert b.load_number == "LD-2"
        assert b.source == "tms"

    def test_manual_and_tms_coexist(self, db_session, org):
        # Per clarifying answer #1: manual rows have no external_id and the
        # TMS upsert must not overwrite or remove them.
        manual = dispatch_repo.create_manual(
            db_session, org_id=org.id, fields={"dispatch_id": "MANUAL-1"}
        )
        tms, _ = dispatch_repo.upsert_from_tms(
            db_session,
            org_id=org.id,
            external_id="ext-tms-1",
            fields={"dispatch_id": "TMS-1"},
        )
        assert manual.id != tms.id
        assert manual.source == "manual"
        assert manual.external_id is None
        assert tms.source == "tms"
        assert tms.external_id == "ext-tms-1"


class TestWeighStationRepo:
    def test_over_limit_derived_from_gross_and_legal_limit(self, db_session, org):
        record = weigh_repo.create_manual(
            db_session,
            org_id=org.id,
            fields={
                "ticket_number": "T-1",
                "gross_weight_lb": 82000,
                "legal_limit_lb": 80000,
            },
        )
        assert record.is_over_legal_limit is True

    def test_explicit_is_over_legal_limit_respected(self, db_session, org):
        record = weigh_repo.create_manual(
            db_session,
            org_id=org.id,
            fields={
                "ticket_number": "T-2",
                "gross_weight_lb": 82000,
                "legal_limit_lb": 80000,
                "is_over_legal_limit": False,
            },
        )
        assert record.is_over_legal_limit is False

    def test_update_recomputes_over_limit(self, db_session, org):
        record = weigh_repo.create_manual(
            db_session,
            org_id=org.id,
            fields={
                "ticket_number": "T-3",
                "gross_weight_lb": 70000,
                "legal_limit_lb": 80000,
            },
        )
        assert record.is_over_legal_limit is False
        weigh_repo.update_manual(
            db_session, report=record, fields={"gross_weight_lb": 85000}
        )
        assert record.is_over_legal_limit is True


class TestLoadingDockRepo:
    def test_attach_artifact_links_photo(self, db_session, org):
        from app.db.models import Incident

        incident = Incident(org_id=org.id, status="open")
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        report = dock_repo.create_manual(
            db_session,
            org_id=org.id,
            fields={"facility_name": "Acme Dock"},
        )
        photo = Artifact(
            org_id=org.id,
            incident_id=incident.incident_id,
            artifact_type="loading_dock_photo",
            status="captured",
        )
        db_session.add(photo)
        db_session.commit()
        db_session.refresh(photo)

        dock_repo.attach_artifact(
            db_session, artifact=photo, loading_dock_report_id=report.id
        )

        photos = dock_repo.list_photos(
            db_session, loading_dock_report_id=report.id
        )
        assert len(photos) == 1
        assert photos[0].artifact_id == photo.artifact_id

    def test_upsert_from_tms_idempotent(self, db_session, org):
        a, created_a = dock_repo.upsert_from_tms(
            db_session,
            org_id=org.id,
            external_id="ext-1",
            fields={
                "facility_name": "Acme Dock",
                "is_overloaded": True,
            },
        )
        assert created_a is True
        b, created_b = dock_repo.upsert_from_tms(
            db_session,
            org_id=org.id,
            external_id="ext-1",
            fields={
                "facility_name": "Acme Dock 2",
                "is_overloaded": False,
            },
        )
        assert created_b is False
        assert a.id == b.id
        assert b.facility_name == "Acme Dock 2"
        assert b.is_overloaded is False
