"""Tests for API endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
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
def no_org_user(db_session):
    user = User(
        email="no-org@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def no_org_auth_headers(no_org_user):
    token = create_access_token({"sub": str(no_org_user.id), "role": no_org_user.role})
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

    def test_get_incident_forbidden_for_other_org(
        self, client, db_session, auth_headers
    ):
        other_org = Org(name="Other Org")
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)
        inc = Incident(status="open", org_id=other_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        resp = client.get(f"/incidents/{inc.incident_id}", headers=auth_headers)
        assert resp.status_code == 403


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


# ── POST /exports ────────────────────────────────────────────────────


class TestRequestExport:
    @patch("app.api.routes_exports.build_export")
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

        resp = client.post(
            "/exports/",
            json={"incident_id": incident_id, "export_type": "court_defense"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "export_id" in data
        assert data["status"] == "queued"
        assert data["incident_id"] == incident_id
        assert data["export_type"] == "court_defense"
        assert data["created_at_utc"] is not None

    @patch("app.api.routes_exports.build_export")
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

        resp = client.post(
            "/exports/",
            json={"incident_id": incident_id, "export_type": "court_defense"},
            headers=auth_headers,
        )
        export_id = resp.json()["export_id"]
        mock_gen.delay.assert_called_once_with(
            incident_id,
            export_id,
            {"attempt_number": 1, "trigger": "api"},
        )

    def test_request_export_incident_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.post(
            "/exports/",
            json={"incident_id": fake_id, "export_type": "court_defense"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_request_export_forbidden_for_other_org_incident(
        self, client, db_session, auth_headers
    ):
        other_org = Org(name="Other Org")
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)
        inc = Incident(status="open", org_id=other_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        resp = client.post(
            "/exports/",
            json={
                "incident_id": str(inc.incident_id),
                "export_type": "court_defense",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_request_export_invalid_type(self, client, db_session, test_org, auth_headers):
        incident = Incident(status="open", org_id=test_org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)
        incident_id = str(incident.incident_id)

        resp = client.post(
            "/exports/",
            json={"incident_id": incident_id, "export_type": "invalid_type"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_request_export_invalid_options_for_court_defense(
        self, client, db_session, test_org, auth_headers
    ):
        incident = Incident(status="open", org_id=test_org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)
        incident_id = str(incident.incident_id)

        resp = client.post(
            "/exports/",
            json={
                "incident_id": incident_id,
                "export_type": "court_defense",
                "options_json": {"profile": "advanced"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @patch("app.api.routes_exports.build_export")
    def test_request_export_accepts_supported_content_options_for_court_defense(
        self, mock_gen, client, db_session, test_org, auth_headers
    ):
        mock_gen.delay = MagicMock()
        incident = Incident(status="open", org_id=test_org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)
        incident_id = str(incident.incident_id)

        resp = client.post(
            "/exports/",
            json={
                "incident_id": incident_id,
                "export_type": "court_defense",
                "options_json": {
                    "profile": "mvp_default",
                    "include_media": False,
                    "include_raw_telemetry": True,
                },
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201


# ── GET /exports/{export_id}/download ───────────────────────────────


class TestDownloadExport:
    def test_download_export_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}/download", headers=auth_headers)
        assert resp.status_code == 404

    def test_download_export_not_ready(
        self, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, org_id=test_org.id, status="requested")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 409

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_ready(
        self, mock_generate_presigned_download_url, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_bucket="my-bucket",
            s3_key="exports/test.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        mock_generate_presigned_download_url.return_value = (
            "https://signed.example.com/exports/test.zip"
        )


        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "url" in data
        assert "signed.example.com" in data["url"]
        mock_generate_presigned_download_url.assert_called_once()
        assert (
            mock_generate_presigned_download_url.call_args.kwargs["expires_in"] == 300
        )

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_logs_event(
        self, mock_generate_presigned_download_url, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        mock_generate_presigned_download_url.return_value = "https://signed.example.com/k"

        client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)

        from app.db.models import Event

        events = (
            db_session.query(Event).filter(Event.incident_id == inc.incident_id).all()
        )
        event_types = [e.event_type for e in events]
        assert "export_downloaded" in event_types
        download_event = next(e for e in events if e.event_type == "export_downloaded")
        assert download_event.payload["export_id"] == str(exp.export_id)
        assert download_event.payload["status"] == "ready"
        assert download_event.payload["actor"]["type"] == "user"
        assert download_event.payload["actor"]["id"]
        assert download_event.payload["downloaded_at_utc"]

    def test_download_export_no_auth_returns_401(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}/download")
        assert resp.status_code in (401, 403)

    def test_download_export_forbidden_for_other_org(
        self, client, db_session, auth_headers, test_org
    ):
        other_org = Org(name="Other Org")
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)

        inc = Incident(status="open", org_id=other_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=other_org.id,
            status="ready",
            s3_bucket="forbidden-bucket",
            s3_key="exports/forbidden.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 403

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_uses_incident_org_for_legacy_null_org_export(
        self, mock_generate_presigned_download_url, client, db_session, auth_headers, test_org
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=None,
            status="ready",
            s3_bucket="legacy-bucket",
            s3_key="exports/legacy.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        mock_generate_presigned_download_url.return_value = (
            "https://signed.example.com/exports/legacy.zip"
        )

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 200

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_missing_bucket_or_key_returns_422(
        self, mock_generate_presigned_download_url, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_bucket=None,
            s3_key=None,
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        from app.services.vault_s3 import S3PresignConfigurationError

        mock_generate_presigned_download_url.side_effect = S3PresignConfigurationError(
            "Export download bucket is not configured"
        )

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 422
        assert resp.json()["detail"] == "Export download bucket is not configured"

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_presign_failure_returns_502(
        self, mock_generate_presigned_download_url, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_bucket="my-bucket",
            s3_key="exports/failure.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        from app.services.vault_s3 import S3PresignGenerationError

        mock_generate_presigned_download_url.side_effect = S3PresignGenerationError(
            "Failed to generate download URL"
        )

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 502
        assert resp.json()["detail"] == "Unable to generate export download URL"

    def test_download_export_forbidden_when_legacy_null_org_export_has_no_org_incident(
        self, client, db_session, auth_headers
    ):
        inc = Incident(status="open", org_id=None)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=None,
            status="ready",
            s3_bucket="legacy-bucket",
            s3_key="exports/legacy.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 403

    def test_download_export_expired_returns_410(
        self, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=test_org.id,
            status="ready",
            s3_bucket="b",
            s3_key="exports/expired.zip",
            expires_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 410
        assert resp.json()["detail"] == "Export is expired"

    @pytest.mark.parametrize("status", ["requested", "queued", "processing", "failed"])
    def test_download_export_not_ready_statuses_return_409(
        self, client, db_session, test_org, auth_headers, status
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, org_id=test_org.id, status=status)
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 409

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_rejects_non_presigned_url(
        self, mock_generate_presigned_download_url, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=test_org.id,
            status="ready",
            s3_bucket="b",
            s3_key="exports/raw.zip",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        mock_generate_presigned_download_url.return_value = (
            "https://bucket.s3.amazonaws.com/exports/raw.zip"
        )

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 502
        assert resp.json()["detail"] == "Invalid presigned download URL"


# ── GET /exports/{export_id} ───────────────────────────────────────


class TestGetExport:
    def test_get_export_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_export_found(self, client, db_session, test_org, auth_headers):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id, org_id=test_org.id, status="requested"
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "requested"

    def test_get_export_downloads_returns_audit_history(
        self, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, org_id=test_org.id, status="ready")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        from app.db.repo.events import create_event

        create_event(
            db_session,
            incident_id=inc.incident_id,
            event_type="export_downloaded",
            actor_type="system",
            actor_id="api",
            payload={"export_id": str(exp.export_id), "status": "ready"},
        )

        resp = client.get(f"/exports/{exp.export_id}/downloads", headers=auth_headers)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["export_id"] == str(exp.export_id)
        assert len(payload["downloads"]) == 1
        assert payload["downloads"][0]["event_type"] == "export_downloaded"
        assert payload["downloads"][0]["actor_type"] == "system"

    def test_get_export_downloads_forbidden_for_other_org(
        self, client, db_session, auth_headers
    ):
        other_org = Org(name="Other Org")
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)

        inc = Incident(status="open", org_id=other_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, org_id=other_org.id, status="ready")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/downloads", headers=auth_headers)
        assert resp.status_code == 403

    def test_get_export_no_auth_returns_401(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/exports/{fake_id}")
        assert resp.status_code in (401, 403)

    def test_get_export_forbidden_for_other_org(
        self, client, db_session, auth_headers
    ):
        other_org = Org(name="Other Org")
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)

        inc = Incident(status="open", org_id=other_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(incident_id=inc.incident_id, org_id=other_org.id, status="ready")
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}", headers=auth_headers)
        assert resp.status_code == 403

    def test_get_export_uses_incident_org_for_legacy_null_org_export(
        self, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=None,
            status="requested",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_export_forbidden_when_legacy_null_org_export_has_no_org_incident(
        self, client, db_session, auth_headers
    ):
        inc = Incident(status="open", org_id=None)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=None,
            status="requested",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}", headers=auth_headers)
        assert resp.status_code == 403


class TestExportStatusAndContents:
    @pytest.mark.parametrize(
        ("status", "progress_stage", "error_message"),
        [
            ("ready", "ready_for_download", None),
            ("processing", "assembling_documents", None),
            ("failed", "packaging_evidence", "zip generation failed"),
        ],
    )
    def test_get_export_status_returns_expected_states(
        self,
        client,
        db_session,
        test_org,
        auth_headers,
        status,
        progress_stage,
        error_message,
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=test_org.id,
            status=status,
            progress_stage=progress_stage,
            error_message=error_message,
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/status", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {
            "status": status,
            "progress_stage": progress_stage,
            "error_message": error_message,
        }

    def test_get_export_contents_returns_manifest_with_stable_kinds(
        self, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        db_session.add_all(
            [
                Artifact(
                    incident_id=inc.incident_id,
                    org_id=test_org.id,
                    artifact_type="photo",
                    status="captured",
                    byte_size=2048,
                ),
                Artifact(
                    incident_id=inc.incident_id,
                    org_id=test_org.id,
                    artifact_type="eld_log",
                    status="captured",
                    byte_size=4096,
                ),
            ]
        )
        exp = Export(
            incident_id=inc.incident_id,
            org_id=test_org.id,
            status="ready",
            progress_stage="ready_for_download",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/contents", headers=auth_headers)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["export_id"] == str(exp.export_id)
        assert payload["status"] == "ready"
        manifest_by_kind = {row["kind"]: row for row in payload["file_manifest"]}
        assert set(manifest_by_kind.keys()) == {"summary_pdf", "raw_telemetry", "photo"}
        assert manifest_by_kind["summary_pdf"]["included"] is True
        assert manifest_by_kind["summary_pdf"]["classification"] == "included"
        assert manifest_by_kind["raw_telemetry"]["included"] is True
        assert manifest_by_kind["raw_telemetry"]["byte_size"] == 4096
        assert manifest_by_kind["photo"]["included"] is True
        assert manifest_by_kind["photo"]["byte_size"] == 2048
        assert payload["missing_items"] == []
        assert payload["warnings"] == []

    def test_export_status_and_contents_forbidden_for_other_org(
        self, client, db_session, auth_headers
    ):
        other_org = Org(name="Other Org")
        db_session.add(other_org)
        db_session.commit()
        db_session.refresh(other_org)

        inc = Incident(status="open", org_id=other_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=other_org.id,
            status="processing",
            progress_stage="assembling_documents",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        status_resp = client.get(f"/exports/{exp.export_id}/status", headers=auth_headers)
        contents_resp = client.get(
            f"/exports/{exp.export_id}/contents", headers=auth_headers
        )
        assert status_resp.status_code == 403
        assert contents_resp.status_code == 403

    def test_export_status_and_contents_legacy_null_org_fallback_to_incident_org(
        self, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=None,
            status="processing",
            progress_stage="assembling_documents",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        status_resp = client.get(f"/exports/{exp.export_id}/status", headers=auth_headers)
        contents_resp = client.get(
            f"/exports/{exp.export_id}/contents", headers=auth_headers
        )
        assert status_resp.status_code == 200
        assert contents_resp.status_code == 200


class TestListExports:
    def test_list_exports_no_org_links_returns_empty(self, client, no_org_auth_headers):
        resp = client.get("/exports/", headers=no_org_auth_headers)
        assert resp.status_code == 403

    def test_get_export_denied_for_user_with_no_org_links(
        self, client, db_session, test_org, no_org_auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=test_org.id,
            status="requested",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}", headers=no_org_auth_headers)
        assert resp.status_code == 403

    def test_list_exports_includes_direct_and_legacy_org_scoped_rows(
        self, client, db_session, test_org, auth_headers
    ):
        visible_incident = Incident(status="open", org_id=test_org.id)
        other_incident = Incident(status="open", org_id=uuid.uuid4())
        db_session.add_all([visible_incident, other_incident])
        db_session.commit()
        db_session.refresh(visible_incident)
        db_session.refresh(other_incident)

        now = datetime.now(timezone.utc)
        direct_export = Export(
            incident_id=visible_incident.incident_id,
            org_id=test_org.id,
            status="ready",
            created_at_utc=now - timedelta(minutes=10),
        )
        legacy_visible_export = Export(
            incident_id=visible_incident.incident_id,
            org_id=None,
            status="processing",
            created_at_utc=now - timedelta(minutes=5),
        )
        legacy_hidden_export = Export(
            incident_id=other_incident.incident_id,
            org_id=None,
            status="failed",
            created_at_utc=now,
        )
        db_session.add_all([direct_export, legacy_visible_export, legacy_hidden_export])
        db_session.commit()
        db_session.refresh(direct_export)
        db_session.refresh(legacy_visible_export)

        resp = client.get("/exports/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert len(data) == 2
        assert [row["export_id"] for row in data] == [
            str(legacy_visible_export.export_id),
            str(direct_export.export_id),
        ]
        assert data[0]["incident_id"] == str(visible_incident.incident_id)
        assert data[0]["status"] == "processing"
        assert "created_at_utc" in data[0]


# ── Health check ────────────────────────────────────────────────────


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
