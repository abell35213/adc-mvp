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
    DispatchInstruction,
    Driver,
    Event,
    Incident,
    LoadingDockReport,
    Org,
    OrgVehicleRegistry,
    WeighStationReport,
)
from app.services.crash_packet_query import (
    MAINTENANCE_LOOKBACK_DAYS,
    SAMSARA_DEEP_LINK_BASE,
    TRIP_CONTEXT_FALLBACK_HOURS,
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

    def test_weather_context_uses_latest_weather_event_without_affecting_count(
        self, db_session, seeded
    ):
        incident = seeded["incident"]
        old_failed_at = datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc)
        latest_captured_at = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        db_session.add_all(
            [
                Event(
                    incident_id=incident.incident_id,
                    event_type="weather_snapshot_failed",
                    actor_type="system",
                    actor_id="weather",
                    occurred_at_utc=old_failed_at,
                    payload={"capture_status": "unavailable"},
                ),
                Event(
                    incident_id=incident.incident_id,
                    event_type="incident_note_added",
                    actor_type="operator",
                    actor_id="ops",
                    occurred_at_utc=latest_captured_at + timedelta(minutes=5),
                    payload={"note": "newer non-weather event"},
                ),
                Event(
                    incident_id=incident.incident_id,
                    event_type="weather_snapshot_captured",
                    actor_type="system",
                    actor_id="weather",
                    occurred_at_utc=latest_captured_at,
                    payload={
                        "capture_status": "captured",
                        "normalized_weather": {"temperature_f": 72},
                        "raw_source_metadata": {"provider": "open-meteo"},
                        "location": {"source": "incident_address"},
                    },
                ),
            ]
        )
        db_session.commit()

        row = fetch_crash_packet_row(db_session, incident_id=incident.incident_id)

        assert row.related_event_count == 4
        assert row.current_weather_conditions_json is not None
        assert row.current_weather_conditions_json["capture_status"] == "captured"
        assert row.current_weather_conditions_json["normalized_weather"] == {
            "temperature_f": 72
        }
        assert row.current_weather_conditions_json["captured_at_utc"].startswith(
            "2026-05-01T12:00:00"
        )


class TestPhase3DispatchWeighDock:
    """Phase 3: dispatch / weigh / loading dock evidence on the crash brief."""

    def test_constants_aligned_with_clarifying_answers(self):
        # Per clarifying answer #3: 24h trip-context fallback window.
        assert TRIP_CONTEXT_FALLBACK_HOURS == 24

    def test_direct_fk_dispatch_instruction(self, db_session, seeded):
        incident = seeded["incident"]
        di = DispatchInstruction(
            org_id=seeded["org"].id,
            incident_id=incident.incident_id,
            adc_driver_id=str(seeded["driver"].driver_id),
            dispatch_id="DSP-001",
            load_number="LD-9001",
            dispatched_at_utc=incident.created_at_utc - timedelta(hours=2),
            forced_dispatch_flag=True,
            source="manual",
        )
        db_session.add(di)
        db_session.commit()

        row = fetch_crash_packet_row(db_session, incident_id=incident.incident_id)
        assert len(row.dispatch_instructions_json) == 1
        assert row.dispatch_instructions_json[0]["dispatch_id"] == "DSP-001"
        assert row.dispatch_instructions_json[0]["forced_dispatch_flag"] is True

    def test_dispatch_fallback_by_driver_within_24h(self, db_session, seeded):
        incident = seeded["incident"]
        # Older dispatch with no incident_id but matching driver in window.
        di = DispatchInstruction(
            org_id=seeded["org"].id,
            adc_driver_id=str(seeded["driver"].driver_id),
            dispatched_at_utc=incident.created_at_utc - timedelta(hours=6),
            dispatch_id="DSP-FALLBACK",
            source="tms",
            external_id="ext-fallback",
        )
        # Out-of-window dispatch (older than 24h) should not be picked up.
        di_old = DispatchInstruction(
            org_id=seeded["org"].id,
            adc_driver_id=str(seeded["driver"].driver_id),
            dispatched_at_utc=incident.created_at_utc - timedelta(hours=72),
            dispatch_id="DSP-OLD",
            source="tms",
            external_id="ext-old",
        )
        db_session.add_all([di, di_old])
        db_session.commit()

        row = fetch_crash_packet_row(db_session, incident_id=incident.incident_id)
        assert len(row.dispatch_instructions_json) == 1
        assert row.dispatch_instructions_json[0]["dispatch_id"] == "DSP-FALLBACK"

    def test_weigh_station_fallback_by_vehicle_within_24h(
        self, db_session, seeded
    ):
        incident = seeded["incident"]
        ws = WeighStationReport(
            org_id=seeded["org"].id,
            adc_vehicle_id="T-100",
            weighed_at_utc=incident.created_at_utc - timedelta(hours=3),
            station_name="Acme Scale",
            gross_weight_lb=82000,
            legal_limit_lb=80000,
            is_over_legal_limit=True,
            result="cited",
            citation_text="Overweight ticket",
            source="manual",
        )
        db_session.add(ws)
        db_session.commit()

        row = fetch_crash_packet_row(db_session, incident_id=incident.incident_id)
        assert len(row.weigh_station_reports_json) == 1
        ticket = row.weigh_station_reports_json[0]
        assert ticket["station_name"] == "Acme Scale"
        assert ticket["is_over_legal_limit"] is True
        assert ticket["result"] == "cited"

    def test_loading_dock_fallback_with_photos(self, db_session, seeded):
        incident = seeded["incident"]
        # Trailer linkage for fallback.
        incident.adc_trailer_id = "TR-555"
        db_session.commit()

        ld = LoadingDockReport(
            org_id=seeded["org"].id,
            adc_trailer_id="TR-555",
            loaded_at_utc=incident.created_at_utc - timedelta(hours=4),
            facility_name="Acme Loading Dock",
            commodity="Refrigerated produce",
            is_improperly_loaded=True,
            source="manual",
        )
        db_session.add(ld)
        db_session.commit()
        db_session.refresh(ld)

        # Two photos linked many-to-one.
        photo1 = Artifact(
            org_id=seeded["org"].id,
            incident_id=incident.incident_id,
            artifact_type="loading_dock_photo",
            status="captured",
            loading_dock_report_id=ld.id,
        )
        photo2 = Artifact(
            org_id=seeded["org"].id,
            incident_id=incident.incident_id,
            artifact_type="loading_dock_photo",
            status="captured",
            loading_dock_report_id=ld.id,
        )
        # An unrelated artifact must NOT show up in this report's photos.
        unrelated = Artifact(
            org_id=seeded["org"].id,
            incident_id=incident.incident_id,
            artifact_type="dashcam_clip",
            status="captured",
        )
        db_session.add_all([photo1, photo2, unrelated])
        db_session.commit()

        row = fetch_crash_packet_row(db_session, incident_id=incident.incident_id)
        assert len(row.loading_dock_reports_json) == 1
        report = row.loading_dock_reports_json[0]
        assert report["facility_name"] == "Acme Loading Dock"
        assert report["is_improperly_loaded"] is True
        assert len(report["photos"]) == 2
        assert all(p["artifact_type"] == "loading_dock_photo" for p in report["photos"])

    def test_no_records_returns_empty_lists(self, db_session, seeded):
        row = fetch_crash_packet_row(
            db_session, incident_id=seeded["incident"].incident_id
        )
        assert row.dispatch_instructions_json == []
        assert row.weigh_station_reports_json == []
        assert row.loading_dock_reports_json == []

    def test_direct_fk_takes_precedence_over_fallback(self, db_session, seeded):
        incident = seeded["incident"]
        # Direct-FK report wins.
        direct = WeighStationReport(
            org_id=seeded["org"].id,
            adc_vehicle_id="T-100",
            incident_id=incident.incident_id,
            weighed_at_utc=incident.created_at_utc - timedelta(hours=20),
            ticket_number="DIRECT",
            source="manual",
        )
        # Fallback candidate that should be ignored because direct match exists.
        fallback = WeighStationReport(
            org_id=seeded["org"].id,
            adc_vehicle_id="T-100",
            weighed_at_utc=incident.created_at_utc - timedelta(hours=2),
            ticket_number="FALLBACK",
            source="manual",
        )
        db_session.add_all([direct, fallback])
        db_session.commit()

        row = fetch_crash_packet_row(db_session, incident_id=incident.incident_id)
        ticket_numbers = [
            r["ticket_number"] for r in row.weigh_station_reports_json
        ]
        assert ticket_numbers == ["DIRECT"]
