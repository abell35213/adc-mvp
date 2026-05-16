from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Artifact, Base, Event, Incident, Org
from app.services.weather.map_snapshot_service import (
    WEATHER_MAP_ARTIFACT_TYPE,
    _fetch_twc_latest_radar_metadata,
    capture_weather_map_snapshot_if_missing,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def incident(db_session):
    org = Org(name="Acme", sms_enabled=False, voice_enabled=False)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    record = Incident(org_id=org.id, status="open")
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def test_capture_weather_map_snapshot_success(db_session, incident, monkeypatch):
    monkeypatch.setattr(
        "app.services.weather.map_snapshot_service.resolve_incident_location",
        lambda *args, **kwargs: {"lat": 40.0, "lon": -74.0, "source": "test", "fallback_reason": None},
    )
    class Rendered:
        image_bytes = b"jpeg-bytes"
        content_type = "image/jpeg"
        overlay_applied = True
        overlay_reason = None
        twc_timestamp_iso = "2026-05-16T10:00:00Z"

    monkeypatch.setattr("app.services.weather.map_snapshot_service.render_map_snapshot", lambda **kwargs: Rendered())
    monkeypatch.setattr("app.services.weather.map_snapshot_service.VaultS3.put_bytes", lambda self, key, data, metadata=None: f"s3://{self.bucket}/{key}")

    capture_weather_map_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
        request_window_end=datetime(2026, 5, 16, 11, 0, tzinfo=timezone.utc),
    )

    artifact = db_session.query(Artifact).filter(Artifact.incident_id == incident.incident_id).one()
    assert artifact.artifact_type == WEATHER_MAP_ARTIFACT_TYPE
    assert artifact.status == "captured"
    assert artifact.s3_key.endswith(".jpg")

    events = db_session.query(Event).filter(Event.incident_id == incident.incident_id).all()
    assert [e.event_type for e in events] == ["weather_map_snapshot_requested", "weather_map_snapshot_captured"]


def test_capture_weather_map_snapshot_overlay_unavailable_degraded(db_session, incident, monkeypatch):
    monkeypatch.setattr(
        "app.services.weather.map_snapshot_service.resolve_incident_location",
        lambda *args, **kwargs: {"lat": 40.0, "lon": -74.0, "source": "test", "fallback_reason": None},
    )

    class Rendered:
        image_bytes = b"jpeg-bytes"
        content_type = "image/jpeg"
        overlay_applied = False
        overlay_reason = "twc_timeslice_empty"
        twc_timestamp_iso = None

    monkeypatch.setattr("app.services.weather.map_snapshot_service.render_map_snapshot", lambda **kwargs: Rendered())
    monkeypatch.setattr("app.services.weather.map_snapshot_service.VaultS3.put_bytes", lambda self, key, data, metadata=None: f"s3://{self.bucket}/{key}")

    capture_weather_map_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
        request_window_end=datetime(2026, 5, 16, 11, 0, tzinfo=timezone.utc),
    )

    captured_event = (
        db_session.query(Event)
        .filter(Event.incident_id == incident.incident_id, Event.event_type == "weather_map_snapshot_captured")
        .one()
    )
    assert captured_event.payload["capture_status"] == "degraded"
    assert captured_event.payload["overlay_unavailable_reason"] == "twc_timeslice_empty"


def test_capture_weather_map_snapshot_failure_links_reason(db_session, incident, monkeypatch):
    monkeypatch.setattr(
        "app.services.weather.map_snapshot_service.resolve_incident_location",
        lambda *args, **kwargs: {"lat": 40.0, "lon": -74.0, "source": "test", "fallback_reason": None},
    )
    monkeypatch.setattr("app.services.weather.map_snapshot_service.render_map_snapshot", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    capture_weather_map_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
        request_window_end=datetime(2026, 5, 16, 11, 0, tzinfo=timezone.utc),
    )

    failed_event = (
        db_session.query(Event)
        .filter(Event.incident_id == incident.incident_id, Event.event_type == "weather_map_snapshot_failed")
        .one()
    )
    assert failed_event.payload["reason"] == "RuntimeError"
    assert db_session.query(Artifact).filter(Artifact.incident_id == incident.incident_id).count() == 0


def test_capture_weather_map_snapshot_resolver_failure_emits_failed_event(db_session, incident, monkeypatch):
    monkeypatch.setattr("app.services.weather.map_snapshot_service.resolve_incident_location", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("nope")))

    capture_weather_map_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
        request_window_end=datetime(2026, 5, 16, 11, 0, tzinfo=timezone.utc),
    )

    failed_event = (
        db_session.query(Event)
        .filter(Event.incident_id == incident.incident_id, Event.event_type == "weather_map_snapshot_failed")
        .one()
    )
    assert failed_event.payload["reason"] == "ValueError"
    assert db_session.query(Artifact).filter(Artifact.incident_id == incident.incident_id).count() == 0


def test_fetch_twc_latest_radar_metadata_uses_api_key_and_latest_first(monkeypatch):
    captured = {}

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"seriesInfo": {"radar": {"series": [{"url": "new"}, {"url": "old"}]}}}

    def fake_get(url, params, timeout):
        captured["params"] = params
        return MockResponse()

    monkeypatch.setattr("app.services.weather.map_snapshot_service.settings.TWC_API_KEY", "twc-key")
    monkeypatch.setattr("app.services.weather.map_snapshot_service.httpx.get", fake_get)

    metadata = _fetch_twc_latest_radar_metadata(lat=1.0, lon=2.0)
    assert captured["params"]["apiKey"] == "twc-key"
    assert metadata["url"] == "new"
