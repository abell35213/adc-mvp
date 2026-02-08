"""Tests for API endpoints."""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Incident, Artifact, Export
from app.db.session import get_db
from app.main import app


# ── Test DB fixtures ────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── POST /incidents ─────────────────────────────────────────────────

class TestCreateIncident:
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_create_incident_returns_201(self, mock_dash, mock_tele, client):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        resp = client.post("/incidents/", json={
            "severity": "serious",
            "adc_vehicle_id": "veh-123",
            "samsara_vehicle_id": "sm-veh-987",
            "adc_driver_id": "drv-555",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "incident_id" in data
        assert data["status"] == "evidence_capturing"

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_create_incident_enqueues_tasks(self, mock_dash, mock_tele, client):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        resp = client.post("/incidents/", json={
            "severity": "minor",
            "adc_vehicle_id": "v1",
            "samsara_vehicle_id": "s1",
            "adc_driver_id": "d1",
        })
        assert resp.status_code == 201
        incident_id = resp.json()["incident_id"]
        mock_dash.delay.assert_called_once_with(incident_id, "", "")
        mock_tele.delay.assert_called_once_with(incident_id, "", "")

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_create_incident_writes_events(self, mock_dash, mock_tele, client, db_session):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        resp = client.post("/incidents/", json={
            "severity": "serious",
            "adc_vehicle_id": "veh-1",
            "samsara_vehicle_id": "sm-1",
            "adc_driver_id": "drv-1",
        })
        assert resp.status_code == 201

        from app.db.models import Event
        events = db_session.query(Event).all()
        event_types = [e.event_type for e in events]
        assert "incident_started" in event_types
        assert "evidence_lockdown_started" in event_types

    def test_create_incident_missing_field_returns_422(self, client):
        resp = client.post("/incidents/", json={
            "severity": "serious",
        })
        assert resp.status_code == 422


# ── GET /incidents/{incident_id} ────────────────────────────────────

class TestGetIncident:
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_get_incident_returns_detail(self, mock_dash, mock_tele, client):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        create_resp = client.post("/incidents/", json={
            "severity": "serious",
            "adc_vehicle_id": "veh-123",
            "samsara_vehicle_id": "sm-veh-987",
            "adc_driver_id": "drv-555",
        })
        incident_id = create_resp.json()["incident_id"]

        resp = client.get(f"/incidents/{incident_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == incident_id
        assert data["severity"] == "serious"
        assert data["adc_driver_id"] == "drv-555"
        assert "evidence_inventory" in data
        assert "export_status" in data

    def test_get_incident_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/incidents/{fake_id}")
        assert resp.status_code == 404


# ── POST /incidents/{incident_id}/exports ───────────────────────────

class TestRequestExport:
    @patch("app.api.routes_incidents.build_export")
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_request_export_returns_201(self, mock_dash, mock_tele, mock_gen, client):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()
        mock_gen.delay = MagicMock()

        create_resp = client.post("/incidents/", json={
            "severity": "minor",
            "adc_vehicle_id": "v1",
            "samsara_vehicle_id": "s1",
            "adc_driver_id": "d1",
        })
        incident_id = create_resp.json()["incident_id"]

        resp = client.post(f"/incidents/{incident_id}/exports")
        assert resp.status_code == 201
        data = resp.json()
        assert "export_id" in data
        assert data["status"] == "requested"

    @patch("app.api.routes_incidents.build_export")
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_request_export_enqueues_task(self, mock_dash, mock_tele, mock_gen, client):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()
        mock_gen.delay = MagicMock()

        create_resp = client.post("/incidents/", json={
            "severity": "minor",
            "adc_vehicle_id": "v1",
            "samsara_vehicle_id": "s1",
            "adc_driver_id": "d1",
        })
        incident_id = create_resp.json()["incident_id"]

        resp = client.post(f"/incidents/{incident_id}/exports")
        export_id = resp.json()["export_id"]
        mock_gen.delay.assert_called_once_with(incident_id, export_id)

    def test_request_export_incident_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/incidents/{fake_id}/exports")
        assert resp.status_code == 404


# ── GET /exports/{export_id}/download ───────────────────────────────

class TestDownloadExport:
    def test_download_export_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}/download")
        assert resp.status_code == 404

    def test_download_export_not_ready(self, client, db_session):
        inc = Incident(status="open")
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, status="requested")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download")
        assert resp.status_code == 409

    def test_download_export_ready(self, client, db_session):
        inc = Incident(status="open")
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            status="ready",
            s3_bucket="my-bucket",
            s3_key="exports/test.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "url" in data
        assert "my-bucket" in data["url"]

    def test_download_export_logs_event(self, client, db_session):
        inc = Incident(status="open")
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            status="ready",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        client.get(f"/exports/{exp.export_id}/download")

        from app.db.models import Event
        events = db_session.query(Event).filter(
            Event.incident_id == inc.incident_id
        ).all()
        event_types = [e.event_type for e in events]
        assert "export_downloaded" in event_types


# ── GET /exports/{export_id} ───────────────────────────────────────

class TestGetExport:
    def test_get_export_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}")
        assert resp.status_code == 404

    def test_get_export_found(self, client, db_session):
        inc = Incident(status="open")
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, status="requested")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "requested"


# ── Health check ────────────────────────────────────────────────────

class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
