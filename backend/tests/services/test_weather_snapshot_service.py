from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Event, Incident, Org
from app.services.weather_snapshot_service import capture_weather_snapshot_if_missing


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def incident(db_session):
    org = Org(name="Weather Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    record = Incident(org_id=org.id, status="open")
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def _window() -> tuple[datetime, datetime]:
    return (
        datetime(2026, 1, 2, 11, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc),
    )


def _event_payloads_by_type(db_session, incident: Incident) -> dict[str, dict]:
    events = (
        db_session.query(Event)
        .filter(Event.incident_id == incident.incident_id)
        .all()
    )
    return {event.event_type: event.payload for event in events}


def test_capture_weather_snapshot_persists_location_source_and_degraded_partial_payload(
    db_session,
    incident,
    monkeypatch,
):
    begin, end = _window()

    monkeypatch.setattr(
        "app.services.weather_snapshot_service.resolve_incident_location",
        lambda *args, **kwargs: {
            "lat": 40.0,
            "lon": -74.0,
            "source": "eld_last_known",
            "fallback_reason": None,
        },
    )
    monkeypatch.setattr(
        "app.services.weather_snapshot_service.fetch_nws_time_series_xml",
        lambda **kwargs: (
            "<dwml><data><parameters><temp><value>72</value></temp></parameters></data></dwml>"
        ),
    )

    capture_weather_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=begin,
        request_window_end=end,
    )

    payloads_by_type = _event_payloads_by_type(db_session, incident)
    assert payloads_by_type["weather_snapshot_requested"]["location"] == {
        "lat": 40.0,
        "lon": -74.0,
        "source": "eld_last_known",
        "fallback_reason": None,
    }
    captured = payloads_by_type["weather_snapshot_captured"]
    assert captured["capture_status"] == "degraded"
    assert captured["degraded"] is True
    assert captured["normalized_weather"]["weather"]["temp"] == {
        "values": ["72"],
        "present": True,
    }
    assert "qpf" in captured["normalized_weather"]["missing_fields"]


def test_capture_weather_snapshot_external_fetch_failure_is_non_blocking(
    db_session,
    incident,
    monkeypatch,
):
    begin, end = _window()
    monkeypatch.setattr(
        "app.services.weather_snapshot_service.resolve_incident_location",
        lambda *args, **kwargs: {
            "lat": 40.0,
            "lon": -74.0,
            "source": "device_location",
            "fallback_reason": None,
        },
    )
    monkeypatch.setattr(
        "app.services.weather_snapshot_service.fetch_nws_time_series_xml",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("nws down")),
    )

    capture_weather_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=begin,
        request_window_end=end,
    )

    events = (
        db_session.query(Event).filter(Event.incident_id == incident.incident_id).all()
    )
    assert [event.event_type for event in events] == [
        "weather_snapshot_requested",
        "weather_snapshot_failed",
    ]
    assert events[1].payload["reason"] == "RuntimeError"
    assert events[1].payload["degraded"] is False


def test_capture_weather_snapshot_skips_duplicate_terminal_event(
    db_session,
    incident,
    monkeypatch,
):
    begin, end = _window()
    fetch_calls = {"count": 0}

    monkeypatch.setattr(
        "app.services.weather_snapshot_service.resolve_incident_location",
        lambda *args, **kwargs: {
            "lat": 40.0,
            "lon": -74.0,
            "source": "device_location",
            "fallback_reason": None,
        },
    )

    def fake_fetch(**kwargs):
        fetch_calls["count"] += 1
        return "<dwml><data><parameters><temp><value>72</value></temp></parameters></data></dwml>"

    monkeypatch.setattr(
        "app.services.weather_snapshot_service.fetch_nws_time_series_xml", fake_fetch
    )

    capture_weather_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=begin,
        request_window_end=end,
    )
    capture_weather_snapshot_if_missing(
        db_session,
        incident=incident,
        request_window_start=begin,
        request_window_end=end,
    )

    assert fetch_calls["count"] == 1
    assert (
        db_session.query(Event)
        .filter(Event.incident_id == incident.incident_id)
        .count()
        == 2
    )
