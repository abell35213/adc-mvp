import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Event, Incident, Org
from app.domain.system_event_types import SystemEventType
from app.services import incident_location_resolver as resolver


class _Provider:
    def __init__(self, gps_rows, state_rows):
        self._gps_rows = gps_rows
        self._state_rows = state_rows

    def fetch_gps_window(self, start=None, end=None):
        return self._gps_rows

    def fetch_vehicle_state(self, start=None, end=None):
        return self._state_rows


class _RecordingProvider:
    def __init__(self, gps_rows, state_rows):
        self._gps_rows = gps_rows
        self._state_rows = state_rows
        self.calls = []

    def fetch_gps_window(self, start=None, end=None):
        self.calls.append(("gps", start, end))
        return self._gps_rows

    def fetch_vehicle_state(self, start=None, end=None):
        self.calls.append(("state", start, end))
        return self._state_rows


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _incident(session: Session, *, adc_vehicle_id: str = "veh-1") -> Incident:
    org = Org(name="Test Org")
    session.add(org)
    session.flush()
    incident = Incident(org_id=org.id, adc_vehicle_id=adc_vehicle_id)
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def test_prefers_device_location(monkeypatch):
    db = _db_session()
    incident = _incident(db)
    db.add(
        Event(
            org_id=incident.org_id,
            incident_id=incident.incident_id,
            event_type=SystemEventType.INCIDENT_PROTOCOL_INITIATED.value,
            actor_type="driver_app",
            actor_id=str(uuid.uuid4()),
            payload={"device_location": {"lat": 10.5, "lon": -20.25}},
        )
    )
    db.commit()

    monkeypatch.setattr(
        resolver,
        "get_telematics_provider",
        lambda: _Provider(
            gps_rows=[{"vehicleId": "veh-1", "lat": 1, "lon": 2}], state_rows=[]
        ),
    )

    result = resolver.resolve_incident_location(db, incident_id=incident.incident_id)
    assert result == {
        "lat": 10.5,
        "lon": -20.25,
        "source": "device_location",
        "fallback_reason": None,
    }


def test_falls_back_to_eld_current(monkeypatch):
    db = _db_session()
    incident = _incident(db)
    monkeypatch.setattr(
        resolver,
        "get_telematics_provider",
        lambda: _Provider(
            gps_rows=[{"vehicleId": "veh-1", "latitude": 33.1, "longitude": -97.2}],
            state_rows=[],
        ),
    )

    result = resolver.resolve_incident_location(db, incident_id=incident.incident_id)
    assert result["source"] == "eld_current"
    assert result["lat"] == 33.1
    assert result["lon"] == -97.2
    assert result["fallback_reason"] is None


def test_falls_back_to_last_known(monkeypatch):
    db = _db_session()
    incident = _incident(db)
    monkeypatch.setattr(
        resolver,
        "get_telematics_provider",
        lambda: _Provider(
            gps_rows=[], state_rows=[{"vehicleId": "veh-1", "lat": 44.0, "lon": -88.0}]
        ),
    )

    result = resolver.resolve_incident_location(db, incident_id=incident.incident_id)
    assert result["source"] == "eld_last_known"
    assert result["lat"] == 44.0
    assert result["lon"] == -88.0


def test_returns_unavailable_sentinel(monkeypatch):
    db = _db_session()
    incident = _incident(db)
    monkeypatch.setattr(
        resolver,
        "get_telematics_provider",
        lambda: _Provider(gps_rows=[], state_rows=[]),
    )

    result = resolver.resolve_incident_location(db, incident_id=incident.incident_id)
    assert result == {
        "lat": None,
        "lon": None,
        "source": "unavailable",
        "fallback_reason": "no_location_available",
    }


def test_does_not_match_telematics_rows_without_incident_vehicle_ids(monkeypatch):
    db = _db_session()
    incident = _incident(db, adc_vehicle_id=None)
    monkeypatch.setattr(
        resolver,
        "get_telematics_provider",
        lambda: _Provider(
            gps_rows=[{"vehicleId": "veh-999", "lat": 40.0, "lon": -74.0}],
            state_rows=[],
        ),
    )

    result = resolver.resolve_incident_location(db, incident_id=incident.incident_id)
    assert result == {
        "lat": None,
        "lon": None,
        "source": "unavailable",
        "fallback_reason": "no_location_available",
    }


def test_telematics_fallback_order_uses_current_before_last_known(monkeypatch):
    db = _db_session()
    incident = _incident(db)
    provider = _RecordingProvider(
        gps_rows=[{"vehicleId": "veh-999", "lat": 1, "lon": 2}],
        state_rows=[{"vehicleId": "veh-1", "lat": 44.0, "lon": -88.0}],
    )
    monkeypatch.setattr(resolver, "get_telematics_provider", lambda: provider)

    result = resolver.resolve_incident_location(db, incident_id=incident.incident_id)

    assert result == {
        "lat": 44.0,
        "lon": -88.0,
        "source": "eld_last_known",
        "fallback_reason": None,
    }
    assert [call[0] for call in provider.calls] == ["gps", "state"]


def test_incident_not_found_returns_unavailable_without_provider_call(monkeypatch):
    db = _db_session()
    provider = _RecordingProvider(gps_rows=[], state_rows=[])
    monkeypatch.setattr(resolver, "get_telematics_provider", lambda: provider)

    result = resolver.resolve_incident_location(db, incident_id=uuid.uuid4())

    assert result == {
        "lat": None,
        "lon": None,
        "source": "unavailable",
        "fallback_reason": "incident_not_found",
    }
    assert provider.calls == []
