"""Tests for API endpoints."""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Incident, Artifact, Export, User, Org, UserOrg
from app.db.session import get_db
from app.core.security import hash_password, create_access_token
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
def test_org(db_session):
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def test_user(db_session, test_org):
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    link = UserOrg(user_id=user.id, org_id=test_org.id)
    db_session.add(link)
    db_session.commit()
    return user


@pytest.fixture()
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id), "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}


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
    def test_create_incident_returns_201(
        self, mock_dash, mock_tele, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
                "adc_vehicle_id": "veh-123",
                "samsara_vehicle_id": "sm-veh-987",
                "adc_driver_id": "drv-555",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "incident_id" in data
        assert data["status"] == "evidence_capturing"

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_create_incident_enqueues_tasks(
        self, mock_dash, mock_tele, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        resp = client.post(
            "/incidents/",
            json={
                "severity": "minor",
                "adc_vehicle_id": "v1",
                "samsara_vehicle_id": "s1",
                "adc_driver_id": "d1",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        incident_id = resp.json()["incident_id"]
        mock_dash.delay.assert_called_once_with(incident_id, "", "")
        mock_tele.delay.assert_called_once_with(incident_id, "", "")

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_create_incident_writes_events(
        self, mock_dash, mock_tele, client, db_session, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
                "adc_vehicle_id": "veh-1",
                "samsara_vehicle_id": "sm-1",
                "adc_driver_id": "drv-1",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201

        from app.db.models import Event

        events = db_session.query(Event).all()
        event_types = [e.event_type for e in events]
        assert "incident_started" in event_types
        assert "evidence_lockdown_started" in event_types

    def test_create_incident_missing_field_returns_422(self, client, auth_headers):
        resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_incident_no_auth_returns_401(self, client):
        resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
                "adc_vehicle_id": "veh-123",
                "samsara_vehicle_id": "sm-veh-987",
                "adc_driver_id": "drv-555",
            },
        )
        assert resp.status_code in (401, 403)


# ── GET /incidents/{incident_id} ────────────────────────────────────


class TestGetIncident:
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_get_incident_returns_detail(
        self, mock_dash, mock_tele, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
                "adc_vehicle_id": "veh-123",
                "samsara_vehicle_id": "sm-veh-987",
                "adc_driver_id": "drv-555",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        resp = client.get(f"/incidents/{incident_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == incident_id
        assert data["severity"] == "serious"
        assert data["adc_driver_id"] == "drv-555"
        assert "evidence_inventory" in data
        assert "export_status" in data

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_get_incident_returns_timeline(
        self, mock_dash, mock_tele, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
                "adc_vehicle_id": "veh-123",
                "samsara_vehicle_id": "sm-veh-987",
                "adc_driver_id": "drv-555",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        resp = client.get(f"/incidents/{incident_id}", headers=auth_headers)
        data = resp.json()
        assert "timeline" in data
        assert len(data["timeline"]) >= 2
        event_types = [e["event_type"] for e in data["timeline"]]
        assert "incident_started" in event_types
        assert "evidence_lockdown_started" in event_types
        for event in data["timeline"]:
            assert "occurred_at_utc" in event
            assert "actor_type" in event

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_get_incident_returns_created_at(
        self, mock_dash, mock_tele, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "minor",
                "adc_vehicle_id": "v1",
                "samsara_vehicle_id": "s1",
                "adc_driver_id": "d1",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        resp = client.get(f"/incidents/{incident_id}", headers=auth_headers)
        data = resp.json()
        assert "created_at_utc" in data

    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_get_incident_artifact_has_extra_fields(
        self, mock_dash, mock_tele, client, db_session, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "serious",
                "adc_vehicle_id": "veh-1",
                "samsara_vehicle_id": "sm-1",
                "adc_driver_id": "drv-1",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        # Add an artifact with unavailable reason
        art = Artifact(
            incident_id=uuid.UUID(incident_id),
            artifact_type="dashcam_road",
            status="unavailable",
            unavailable_reason_code="camera_offline",
        )
        db_session.add(art)
        db_session.commit()

        resp = client.get(f"/incidents/{incident_id}", headers=auth_headers)
        data = resp.json()
        found = [
            a
            for a in data["evidence_inventory"]
            if a["artifact_type"] == "dashcam_road"
        ]
        assert len(found) == 1
        assert found[0]["unavailable_reason"] == "camera_offline"

    def test_get_incident_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/incidents/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


# ── GET /incidents (list) ───────────────────────────────────────────


class TestListIncidents:
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_list_incidents_returns_evidence_counts(
        self, mock_dash, mock_tele, client, db_session, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "minor",
                "adc_vehicle_id": "v1",
                "samsara_vehicle_id": "s1",
                "adc_driver_id": "d1",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        # Add some artifacts
        art1 = Artifact(
            incident_id=uuid.UUID(incident_id),
            artifact_type="dashcam_road",
            status="captured",
        )
        art2 = Artifact(
            incident_id=uuid.UUID(incident_id),
            artifact_type="gps_trace",
            status="pending",
        )
        db_session.add_all([art1, art2])
        db_session.commit()

        resp = client.get("/incidents/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        inc = [i for i in data if i["incident_id"] == incident_id][0]
        assert inc["evidence_captured"] == 1
        assert inc["evidence_total"] == 2
        assert "created_at_utc" in inc


# ── POST /incidents/{incident_id}/exports ───────────────────────────


class TestRequestExport:
    @patch("app.api.routes_incidents.build_export")
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_request_export_returns_201(
        self, mock_dash, mock_tele, mock_gen, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()
        mock_gen.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "minor",
                "adc_vehicle_id": "v1",
                "samsara_vehicle_id": "s1",
                "adc_driver_id": "d1",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        resp = client.post(f"/incidents/{incident_id}/exports", headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "export_id" in data
        assert data["status"] == "requested"

    @patch("app.api.routes_incidents.build_export")
    @patch("app.api.routes_incidents.capture_telematics_bundle")
    @patch("app.api.routes_incidents.capture_dashcam")
    def test_request_export_enqueues_task(
        self, mock_dash, mock_tele, mock_gen, client, auth_headers
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()
        mock_gen.delay = MagicMock()

        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "minor",
                "adc_vehicle_id": "v1",
                "samsara_vehicle_id": "s1",
                "adc_driver_id": "d1",
            },
            headers=auth_headers,
        )
        incident_id = create_resp.json()["incident_id"]

        resp = client.post(f"/incidents/{incident_id}/exports", headers=auth_headers)
        export_id = resp.json()["export_id"]
        mock_gen.delay.assert_called_once_with(incident_id, export_id)

    def test_request_export_incident_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/incidents/{fake_id}/exports", headers=auth_headers)
        assert resp.status_code == 404


# ── GET /exports/{export_id}/download ───────────────────────────────


class TestDownloadExport:
    def test_download_export_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}/download", headers=auth_headers)
        assert resp.status_code == 404

    def test_download_export_not_ready(self, client, db_session, auth_headers):
        inc = Incident(status="open")
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, status="requested")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 409

    def test_download_export_ready(self, client, db_session, auth_headers):
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

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "url" in data
        assert "my-bucket" in data["url"]

    def test_download_export_logs_event(self, client, db_session, auth_headers):
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

        client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)

        from app.db.models import Event

        events = (
            db_session.query(Event).filter(Event.incident_id == inc.incident_id).all()
        )
        event_types = [e.event_type for e in events]
        assert "export_downloaded" in event_types

    def test_download_export_no_auth_returns_401(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}/download")
        assert resp.status_code in (401, 403)


# ── GET /exports/{export_id} ───────────────────────────────────────


class TestGetExport:
    def test_get_export_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_export_found(self, client, db_session, auth_headers):
        inc = Incident(status="open")
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, status="requested")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "requested"

    def test_get_export_no_auth_returns_401(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}")
        assert resp.status_code in (401, 403)


# ── Health check ────────────────────────────────────────────────────


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
