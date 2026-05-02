"""Golden tests for the canonical crash-packet SQL (Phase 1, plan test #1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Artifact,
    Base,
    Driver,
    Event,
    Incident,
    Org,
    OrgVehicleRegistry,
)
from app.services.crash_packet_query import (
    MAINTENANCE_LOOKBACK_DAYS,
    SAMSARA_DEEP_LINK_BASE,
    fetch_crash_packet_row,
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
def seeded(db_session):
    org = Org(name="Acme", sms_enabled=False, voice_enabled=False)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    driver = Driver(
        org_id=org.id,
        phone_e164="+15551234567",
        display_name="Pat Driver",
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)

    vehicle = OrgVehicleRegistry(
        org_id=org.id,
        unit_number="T-100",
        vin="1HGBH41JXMN109186",
        provider="samsara",
        provider_vehicle_id="sams-9001",
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    incident = Incident(
        status="evidence_capturing",
        adc_vehicle_id="T-100",
        samsara_vehicle_id="sams-9001",
        adc_driver_id=str(driver.driver_id),
        severity="serious",
        org_id=org.id,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    # Prior incident for safety history.
    prior = Incident(
        status="closed",
        adc_vehicle_id="T-100",
        adc_driver_id=str(driver.driver_id),
        severity="minor",
        org_id=org.id,
    )
    db_session.add(prior)

    # ELD + dashcam artifacts on the new incident.
    eld_artifact = Artifact(
        org_id=org.id,
        incident_id=incident.incident_id,
        artifact_type="eld_log_report",
        status="captured",
        capture_window_start_utc=datetime(2026, 5, 1, tzinfo=timezone.utc)
        - timedelta(days=2),
        capture_window_end_utc=datetime(2026, 5, 1, tzinfo=timezone.utc),
        s3_bucket="adc-mvp-artifacts",
        s3_key="incidents/x/eld.json",
    )
    dashcam_artifact = Artifact(
        org_id=org.id,
        incident_id=incident.incident_id,
        artifact_type="dashcam_clip",
        status="captured",
        capture_window_start_utc=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        capture_window_end_utc=datetime(2026, 5, 1, 12, 1, tzinfo=timezone.utc),
        s3_bucket="adc-mvp-artifacts",
        s3_key="incidents/x/dashcam.mp4",
    )
    db_session.add_all([eld_artifact, dashcam_artifact])

    # A timeline event so related_event_count is non-zero.
    db_session.add(
        Event(
            incident_id=incident.incident_id,
            event_type="incident_protocol_initiated",
            actor_type="driver_app",
            actor_id="seed",
        )
    )
    db_session.commit()
    return {
        "org": org,
        "driver": driver,
        "vehicle": vehicle,
        "incident": incident,
        "prior": prior,
    }


class TestCrashPacketQuery:
    def test_returns_all_required_sections(self, db_session, seeded):
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )

        assert row.incident_json["incident_id"] == str(seeded["incident"].incident_id)
        assert row.incident_json["severity"] == "serious"
        assert row.driver_json is not None
        assert row.driver_json["display_name"] == "Pat Driver"
        assert row.vehicle_json is not None
        assert row.vehicle_json["unit_number"] == "T-100"
        # Phase 2 will populate trailer + maintenance from TMS cache.
        assert row.trailer_json is None
        assert row.maintenance_json == []
        assert row.related_event_count == 1

    def test_driver_history_excludes_current(self, db_session, seeded):
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )
        history_ids = [h["incident_id"] for h in row.driver_history_json]
        assert str(seeded["incident"].incident_id) not in history_ids
        assert str(seeded["prior"].incident_id) in history_ids

    def test_maintenance_window_is_one_year(self, db_session, seeded):
        # Per clarifying answer: "The maintenance history should be the past
        # year. not 90 days."
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )
        assert row.maintenance_window_days == 365
        assert MAINTENANCE_LOOKBACK_DAYS == 365

    def test_eld_artifacts_surfaced(self, db_session, seeded):
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )
        assert len(row.eld_logs_json) == 1
        assert row.eld_logs_json[0]["artifact_type"] == "eld_log_report"

    def test_samsara_deep_links_built_from_dashcam_artifacts(
        self, db_session, seeded
    ):
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )
        assert len(row.samsara_clip_links_json) == 1
        link = row.samsara_clip_links_json[0]
        assert link["samsara_vehicle_id"] == "sams-9001"
        assert link["deep_link"].startswith(SAMSARA_DEEP_LINK_BASE)
        assert "vehicles/sams-9001/dashcam" in link["deep_link"]
        # Fallback fields preserved (per plan: presigned S3 link as fallback).
        assert link["fallback_s3_bucket"] == "adc-mvp-artifacts"

    def test_dashcam_link_falls_back_when_no_samsara_id(
        self, db_session, seeded
    ):
        seeded["incident"].samsara_vehicle_id = None
        db_session.commit()
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )
        link = row.samsara_clip_links_json[0]
        assert link["samsara_vehicle_id"] is None
        assert link["deep_link"] is None
        assert link["fallback_s3_key"] == "incidents/x/dashcam.mp4"

    def test_unknown_incident_raises(self, db_session):
        with pytest.raises(LookupError):
            fetch_crash_packet_row(db_session, incident_id=uuid.uuid4())
