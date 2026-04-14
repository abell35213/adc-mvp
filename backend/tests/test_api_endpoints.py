"""Tests for API endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    Incident,
    Artifact,
    AuditEvent,
    Event,
    Export,
    User,
    Org,
    UserOrg,
    IntegrationConnection,
    IntegrationOperation,
    EvidenceRequest,
    Driver,
    DriverVehicleAssignment,
    ExternalMapping,
    VehicleQrToken,
    OrgVehicleRegistry,
)
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
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_create_incident_returns_201(
        self, mock_begin_capture, client, auth_headers
    ):
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

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_create_incident_enqueues_tasks(
        self, mock_begin_capture, client, auth_headers
    ):
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
        mock_begin_capture.assert_called_once()
        call_kwargs = mock_begin_capture.call_args.kwargs
        assert str(call_kwargs["incident_id"]) == incident_id

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_create_incident_writes_events(
        self, mock_begin_capture, client, db_session, auth_headers
    ):
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
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_get_incident_returns_detail(
        self, mock_begin_capture, client, auth_headers
    ):
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

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_get_incident_returns_timeline(
        self, mock_begin_capture, client, auth_headers
    ):
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


class TestIncidentExportReadiness:
    @patch("app.api.routes_incidents.build_export.delay")
    @patch("app.api.routes_incidents.build_case_snapshot")
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_incident_export_blocks_not_ready(
        self,
        mock_begin_capture,
        mock_snapshot,
        mock_delay,
        client,
        auth_headers,
    ):
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
        mock_snapshot.return_value = SimpleNamespace(
            readiness=SimpleNamespace(
                state="not_ready", blocking_codes=["evidence_capture_incomplete"]
            ),
            completeness=SimpleNamespace(percent=45, status="incomplete"),
            blockers=SimpleNamespace(
                items=[
                    SimpleNamespace(
                        code="evidence_capture_incomplete",
                        message="Evidence capture incomplete.",
                        severity="critical",
                        blocks_readiness=True,
                    )
                ]
            ),
        )

        resp = client.post(f"/incidents/{incident_id}/exports", headers=auth_headers)
        assert resp.status_code == 409
        payload = resp.json()["detail"]
        assert payload["readiness_state"] == "not_ready"
        assert payload["reasons"][0]["code"] == "evidence_capture_incomplete"
        mock_delay.assert_not_called()

    @patch("app.api.routes_incidents.build_export.delay")
    @patch("app.api.routes_incidents.build_case_snapshot")
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_incident_export_allows_conditionally_ready_and_persists_snapshot(
        self,
        mock_begin_capture,
        mock_snapshot,
        mock_delay,
        client,
        db_session,
        auth_headers,
    ):
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
        mock_snapshot.return_value = SimpleNamespace(
            readiness=SimpleNamespace(
                state="conditionally_ready", blocking_codes=["driver_statement_missing"]
            ),
            completeness=SimpleNamespace(percent=88, status="mostly_complete"),
            blockers=SimpleNamespace(
                items=[
                    SimpleNamespace(
                        code="driver_statement_missing",
                        message="Driver statement still pending.",
                        severity="important",
                        blocks_readiness=False,
                    )
                ]
            ),
        )
        mock_delay.return_value = MagicMock(id="task-123")

        resp = client.post(f"/incidents/{incident_id}/exports", headers=auth_headers)
        assert resp.status_code == 201

        export = db_session.query(Export).one()
        readiness_snapshot = export.options_json.get("readiness_snapshot")
        readiness_warning = export.options_json.get("readiness_warning")
        assert readiness_snapshot["state"] == "conditionally_ready"
        assert readiness_snapshot["blocking_codes"] == ["driver_statement_missing"]
        assert readiness_warning["code"] == "conditional_export_readiness"


class TestIntegrationDiagnosticsRoutes:
    def test_org_settings_read_and_patch(
        self, client, db_session, test_org, auth_headers
    ):
        read = client.get("/org/settings", headers=auth_headers)
        assert read.status_code == 200
        assert read.json()["display_name"] == "Test Org"

        update = client.patch(
            "/org/settings",
            headers=auth_headers,
            json={
                "legal_name": "Test Org LLC",
                "display_name": "Test Org Display",
                "timezone": "America/Chicago",
                "region": "US",
                "contacts": [{"name": "Safety Lead", "email": "safety@test.org"}],
                "implementation_contact": {
                    "name": "Impl Lead",
                    "email": "impl@test.org",
                },
                "logo_url": "https://cdn.example.com/logo.png",
            },
        )
        assert update.status_code == 200
        payload = update.json()
        assert payload["legal_name"] == "Test Org LLC"
        assert payload["display_name"] == "Test Org Display"
        assert payload["timezone"] == "America/Chicago"
        assert payload["contacts"][0]["email"] == "safety@test.org"
        assert payload["implementation_contact"]["email"] == "impl@test.org"
        assert payload["logo_url"] == "https://cdn.example.com/logo.png"

    def test_onboarding_status_and_mark_step(self, client, auth_headers):
        status_before = client.get("/org/onboarding/status", headers=auth_headers)
        assert status_before.status_code == 200

        mark = client.post(
            "/org/onboarding/mark-step",
            headers=auth_headers,
            json={"step_key": "org_settings", "completed": True, "source": "dashboard"},
        )
        assert mark.status_code == 200
        org_settings_step = next(
            item for item in mark.json()["steps"] if item["key"] == "org_settings"
        )
        assert org_settings_step["status"] == "completed"
        assert org_settings_step["metadata"]["completion_source"] == "dashboard"
        assert org_settings_step["metadata"]["completed_by_user_id"]

    def test_users_roles_step_gate_requires_org_admin_and_safety_capable(
        self, client, auth_headers
    ):
        mark = client.post(
            "/org/onboarding/mark-step",
            headers=auth_headers,
            json={"step_key": "users_roles", "completed": True, "source": "dashboard"},
        )
        assert mark.status_code == 409
        detail = mark.json()["detail"]
        assert detail["code"] == "users_roles_prerequisites_not_met"
        assert "no org admin assigned" in detail["violations"]
        assert "no safety manager assigned" not in detail["violations"]

    def test_org_settings_completion_rule_updates_onboarding_status(
        self, client, auth_headers
    ):
        initial = client.get("/org/onboarding/status", headers=auth_headers)
        assert initial.status_code == 200
        initial_step = next(
            item for item in initial.json()["steps"] if item["key"] == "org_settings"
        )
        assert initial_step["status"] in {"blocked", "not_started"}

        updated = client.patch(
            "/org/settings",
            headers=auth_headers,
            json={
                "legal_name": "Acme Transport LLC",
                "display_name": "Acme Transport",
                "timezone": "America/Los_Angeles",
                "region": "US-West",
                "contacts": [{"name": "Jane Safety", "email": "jane@acme.test"}],
                "implementation_contact": {"name": "Bob Ops", "email": "bob@acme.test"},
            },
        )
        assert updated.status_code == 200

        refreshed = client.get("/org/onboarding/status", headers=auth_headers)
        assert refreshed.status_code == 200
        refreshed_step = next(
            item for item in refreshed.json()["steps"] if item["key"] == "org_settings"
        )
        assert refreshed_step["status"] == "completed"

    def test_org_integrations_and_details(
        self, client, db_session, test_org, auth_headers
    ):
        connection = IntegrationConnection(
            org_id=test_org.id,
            provider="samsara",
            domain="telematics",
            status="active",
            credentials_ref="vault://samsara",
        )
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)

        list_resp = client.get("/org/integrations", headers=auth_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        detail_resp = client.get(
            f"/org/integrations/{connection.connection_id}", headers=auth_headers
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["provider"] == "samsara"

    def test_org_users_list_invite_patch_role_resend_deactivate(
        self, client, db_session, test_org, test_user
    ):
        org_admin = User(
            email="org-admin@example.com",
            password_hash=hash_password("password123"),
            role="org_admin",
        )
        db_session.add(org_admin)
        db_session.commit()
        db_session.refresh(org_admin)
        db_session.add(UserOrg(user_id=org_admin.id, org_id=test_org.id))
        db_session.commit()

        admin_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(org_admin.id), 'role': 'org_admin'})}"
        }

        list_resp = client.get("/org/users", headers=admin_headers)
        assert list_resp.status_code == 200
        payload = list_resp.json()
        assert len(payload["users"]) == 2
        assert payload["role_counts"]["org_admin"] == 1
        assert payload["role_counts"]["safety_manager"] == 1
        assert payload["violations"] == []

        invite_resp = client.post(
            "/org/users/invite",
            headers=admin_headers,
            json={"email": "invitee@example.com", "role": "safety_manager"},
        )
        assert invite_resp.status_code == 201
        invite_payload = invite_resp.json()
        assert invite_payload["invite"]["status"] == "pending"
        invite_id = invite_payload["invite"]["invite_id"]

        resend_resp = client.post(
            f"/org/users/invite/{invite_id}/resend",
            headers=admin_headers,
        )
        assert resend_resp.status_code == 200
        assert resend_resp.json()["invite"]["status"] == "pending"

        deactivate_resp = client.post(
            f"/org/users/invite/{invite_id}/deactivate",
            headers=admin_headers,
        )
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["invite"]["status"] == "deactivated"

        patch_role = client.patch(
            f"/org/users/{test_user.id}/role",
            headers=admin_headers,
            json={"role": "org_admin"},
        )
        assert patch_role.status_code == 200
        updated_user = next(
            item
            for item in patch_role.json()["users"]
            if item["user_id"] == str(test_user.id)
        )
        assert updated_user["role"] == "org_admin"

    def test_org_user_admin_permissions_enforced(self, client, auth_headers):
        invite_resp = client.post(
            "/org/users/invite",
            headers=auth_headers,
            json={"email": "invitee@example.com", "role": "safety_manager"},
        )
        assert invite_resp.status_code == 403

    def test_integration_operations_and_evidence_summary(
        self, client, db_session, test_org, test_user, auth_headers
    ):
        incident = Incident(
            org_id=test_org.id,
            status="evidence_capturing",
            severity="serious",
            adc_vehicle_id="veh-123",
            samsara_vehicle_id="sm-veh-123",
            adc_driver_id="drv-123",
        )
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        operation = IntegrationOperation(
            org_id=test_org.id,
            incident_id=incident.incident_id,
            provider="samsara",
            domain="dashcam",
            operation_type="capture_dashcam",
            status="failed",
            payload_json={"token": "abc123", "nested": {"api_key": "very-secret"}},
            result_json={"authorization": "Bearer asdf"},
        )
        db_session.add(operation)
        db_session.commit()
        db_session.refresh(operation)

        evidence = EvidenceRequest(
            org_id=test_org.id,
            incident_id=incident.incident_id,
            operation_id=operation.operation_id,
            provider="samsara",
            domain="dashcam",
            status="failed",
            error_retryable=True,
            request_payload_json={},
            response_payload_json={},
        )
        db_session.add(evidence)
        db_session.commit()

        ops_resp = client.get("/integration-operations", headers=auth_headers)
        assert ops_resp.status_code == 403
        test_user.role = "org_admin"
        db_session.add(test_user)
        db_session.commit()
        org_admin_token = create_access_token(
            {"sub": str(test_user.id), "role": "org_admin"}
        )
        org_admin_headers = {"Authorization": f"Bearer {org_admin_token}"}
        ops_resp = client.get("/integration-operations", headers=org_admin_headers)
        assert ops_resp.status_code == 200
        assert len(ops_resp.json()) == 1
        payload = ops_resp.json()[0]["payload_json"]
        result_payload = ops_resp.json()[0]["result_json"]
        assert payload["token"] == "[REDACTED]"
        assert payload["nested"]["api_key"] == "[REDACTED]"
        assert result_payload["authorization"] == "[REDACTED]"

        evidence_list = client.get(
            f"/incidents/{incident.incident_id}/evidence-requests",
            headers=auth_headers,
        )
        assert evidence_list.status_code == 200
        assert len(evidence_list.json()) == 1

        summary_resp = client.get(
            f"/incidents/{incident.incident_id}/evidence-summary",
            headers=auth_headers,
        )
        assert summary_resp.status_code == 200
        assert summary_resp.json()["retryable_failures"] == 1

    def test_integration_validate_requires_admin_role(
        self,
        client,
        db_session,
        test_org,
        test_user,
        auth_headers,
    ):
        connection = IntegrationConnection(
            org_id=test_org.id,
            provider="twilio",
            domain="messaging",
            status="active",
            credentials_ref="vault://twilio",
        )
        db_session.add(connection)
        db_session.commit()

        denied = client.post(
            f"/org/integrations/{connection.connection_id}/validate",
            headers=auth_headers,
        )
        assert denied.status_code == 403

        test_user.role = "org_admin"
        db_session.add(test_user)
        db_session.commit()
        org_admin_token = create_access_token(
            {"sub": str(test_user.id), "role": "org_admin"}
        )
        org_admin_headers = {"Authorization": f"Bearer {org_admin_token}"}
        allowed = client.post(
            f"/org/integrations/{connection.connection_id}/validate",
            headers=org_admin_headers,
        )
        assert allowed.status_code == 200

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_get_incident_returns_created_at(
        self, mock_begin_capture, client, auth_headers
    ):
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

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_get_incident_artifact_has_extra_fields(
        self, mock_begin_capture, client, db_session, auth_headers
    ):
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
        assert resp.status_code == 404


# ── PATCH /incidents/{incident_id}/status ───────────────────────────


class TestPatchIncidentStatus:
    def _create_incident(self, client, auth_headers) -> str:
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
        assert create_resp.status_code == 201
        return create_resp.json()["incident_id"]

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_patch_incident_status_allows_standard_transition(
        self, mock_begin_capture, client, db_session, auth_headers
    ):
        incident_id = self._create_incident(client, auth_headers)
        incident = (
            db_session.query(Incident)
            .filter(Incident.incident_id == uuid.UUID(incident_id))
            .one()
        )
        incident.case_status = "new"
        db_session.add(incident)
        db_session.commit()

        response = client.patch(
            f"/incidents/{incident_id}/status",
            json={"case_status": "in_review", "reason": "Ready for triage"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["case_status"] == "in_review"

        latest_event = (
            db_session.query(Event)
            .filter(
                Event.incident_id == uuid.UUID(incident_id),
                Event.event_type == "incident_updated",
            )
            .order_by(Event.created_at_utc.desc())
            .first()
        )
        assert latest_event is not None
        assert latest_event.payload["transition_reason"] == "Ready for triage"
        assert latest_event.payload["from_case_status"] == "new"
        assert latest_event.payload["to_case_status"] == "in_review"

        latest_audit = (
            db_session.query(AuditEvent)
            .filter(AuditEvent.incident_id == uuid.UUID(incident_id))
            .order_by(AuditEvent.created_at_utc.desc())
            .first()
        )
        assert latest_audit is not None
        assert latest_audit.metadata_json["transition_reason"] == "Ready for triage"
        assert latest_audit.event_type == "incident_case_status_updated"

        status_event = (
            db_session.query(Event)
            .filter(
                Event.incident_id == uuid.UUID(incident_id),
                Event.event_type == "incident_status_changed",
            )
            .order_by(Event.created_at_utc.desc())
            .first()
        )
        assert status_event is not None
        assert status_event.payload["previous"]["case_status"] == "new"
        assert status_event.payload["new"]["case_status"] == "in_review"
        assert status_event.payload["actor"]["type"] == "user"

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_patch_incident_status_rejects_privileged_transition_without_permission(
        self, mock_begin_capture, client, db_session, auth_headers
    ):
        incident_id = self._create_incident(client, auth_headers)
        incident = (
            db_session.query(Incident)
            .filter(Incident.incident_id == uuid.UUID(incident_id))
            .one()
        )
        incident.case_status = "in_review"
        db_session.add(incident)
        db_session.commit()

        response = client.patch(
            f"/incidents/{incident_id}/status",
            json={"case_status": "closed", "reason": "Investigation complete"},
            headers=auth_headers,
        )
        assert response.status_code == 403

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_patch_incident_status_allows_reopen_for_org_admin(
        self, mock_begin_capture, client, db_session, test_org, auth_headers
    ):
        incident_id = self._create_incident(client, auth_headers)
        incident = (
            db_session.query(Incident)
            .filter(Incident.incident_id == uuid.UUID(incident_id))
            .one()
        )
        incident.case_status = "closed"
        db_session.add(incident)
        org_admin = User(
            email="org-admin-status@example.com",
            password_hash=hash_password("testpass"),
            role="org_admin",
        )
        db_session.add(org_admin)
        db_session.commit()
        db_session.refresh(org_admin)
        db_session.add(UserOrg(user_id=org_admin.id, org_id=test_org.id))
        db_session.commit()

        org_admin_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(org_admin.id), 'role': 'org_admin'})}"
        }

        response = client.patch(
            f"/incidents/{incident_id}/status",
            json={"case_status": "in_review", "reason": "Reopened for legal review"},
            headers=org_admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["case_status"] == "in_review"
        assert response.json()["transition_reason"] == "Reopened for legal review"


# ── PATCH /incidents/{incident_id}/owner ───────────────────────────


class TestPatchIncidentOwner:
    def _create_incident(self, client, auth_headers) -> str:
        create_resp = client.post(
            "/incidents/",
            json={
                "severity": "minor",
                "adc_vehicle_id": "owner-v1",
                "samsara_vehicle_id": "owner-s1",
                "adc_driver_id": "owner-d1",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        return create_resp.json()["incident_id"]

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_patch_owner_assign_reassign_clear(
        self, mock_begin_capture, client, db_session, test_org, auth_headers
    ):
        incident_id = self._create_incident(client, auth_headers)

        owner_one = User(
            email="owner-one@example.com",
            password_hash=hash_password("testpass"),
            role="safety_manager",
        )
        owner_two = User(
            email="owner-two@example.com",
            password_hash=hash_password("testpass"),
            role="safety_manager",
        )
        db_session.add_all([owner_one, owner_two])
        db_session.commit()
        db_session.refresh(owner_one)
        db_session.refresh(owner_two)
        db_session.add_all(
            [
                UserOrg(user_id=owner_one.id, org_id=test_org.id),
                UserOrg(user_id=owner_two.id, org_id=test_org.id),
            ]
        )
        db_session.commit()

        assign_resp = client.patch(
            f"/incidents/{incident_id}/owner",
            json={"operation": "assign", "owner_user_id": str(owner_one.id)},
            headers=auth_headers,
        )
        assert assign_resp.status_code == 200
        assign_payload = assign_resp.json()
        assert assign_payload["owner_user_id"] == str(owner_one.id)
        assert assign_payload["assigned_by"] is not None
        assert assign_payload["assigned_at"] is not None
        assert assign_payload["last_activity_at_utc"] is not None

        reassign_resp = client.patch(
            f"/incidents/{incident_id}/owner",
            json={"operation": "reassign", "owner_user_id": str(owner_two.id)},
            headers=auth_headers,
        )
        assert reassign_resp.status_code == 200
        reassign_payload = reassign_resp.json()
        assert reassign_payload["owner_user_id"] == str(owner_two.id)
        assert reassign_payload["assigned_by"] is not None
        assert reassign_payload["assigned_at"] is not None
        assert reassign_payload["last_activity_at_utc"] is not None

        clear_resp = client.patch(
            f"/incidents/{incident_id}/owner",
            json={"operation": "clear"},
            headers=auth_headers,
        )
        assert clear_resp.status_code == 200
        clear_payload = clear_resp.json()
        assert clear_payload["owner_user_id"] is None
        assert clear_payload["assigned_by"] is None
        assert clear_payload["assigned_at"] is None
        assert clear_payload["team_queue"] == "Unassigned"
        assert clear_payload["last_activity_at_utc"] is not None

        incident = (
            db_session.query(Incident)
            .filter(Incident.incident_id == uuid.UUID(incident_id))
            .one()
        )
        assert incident.owner_user_id is None
        assert incident.owner_assigned_at_utc is None
        assert incident.owner_assigned_by_user_id is None
        assert incident.team_queue == "Unassigned"
        assert incident.last_activity_at_utc is not None

        event_types = {
            e.event_type
            for e in db_session.query(Event)
            .filter(Event.incident_id == uuid.UUID(incident_id))
            .all()
        }
        assert {
            "incident_owner_assigned",
            "incident_owner_reassigned",
            "incident_owner_cleared",
        }.issubset(event_types)

        audit_types = {
            e.event_type
            for e in db_session.query(AuditEvent)
            .filter(AuditEvent.incident_id == uuid.UUID(incident_id))
            .all()
        }
        assert {
            "incident_owner_assigned",
            "incident_owner_reassigned",
            "incident_owner_cleared",
        }.issubset(audit_types)

    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_patch_owner_enforces_org_isolation(
        self, mock_begin_capture, client, db_session, auth_headers
    ):
        incident_id = self._create_incident(client, auth_headers)
        other_org = Org(name="Other Owner Org")
        foreign_owner = User(
            email="foreign-owner@example.com",
            password_hash=hash_password("testpass"),
            role="safety_manager",
        )
        db_session.add_all([other_org, foreign_owner])
        db_session.commit()
        db_session.refresh(other_org)
        db_session.refresh(foreign_owner)
        db_session.add(UserOrg(user_id=foreign_owner.id, org_id=other_org.id))
        db_session.commit()

        response = client.patch(
            f"/incidents/{incident_id}/owner",
            json={"operation": "assign", "owner_user_id": str(foreign_owner.id)},
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Owner user not found"


# ── GET /incidents (list) ───────────────────────────────────────────


class TestListIncidents:
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_list_incidents_returns_evidence_counts(
        self, mock_begin_capture, client, db_session, auth_headers
    ):
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
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_request_export_returns_201(
        self, mock_begin_capture, mock_gen, client, auth_headers
    ):
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
    @patch("app.api.routes_incidents.IncidentEvidenceOrchestrator.begin_capture")
    def test_request_export_enqueues_task(
        self, mock_begin_capture, mock_gen, client, auth_headers
    ):
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

    def test_request_export_invalid_type(
        self, client, db_session, test_org, auth_headers
    ):
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
                "options_json": {"profile_id": "advanced"},
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
                    "profile_id": "court_defense_v1",
                    "include_media": False,
                    "include_raw_telemetry": True,
                },
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201

    @patch("app.api.routes_exports.build_export")
    def test_retry_failed_export_creates_linked_attempt_and_reuses_config(
        self, mock_gen, client, db_session, test_org, test_user, auth_headers
    ):
        mock_gen.delay = MagicMock()
        incident = Incident(status="open", org_id=test_org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        failed = Export(
            incident_id=incident.incident_id,
            org_id=test_org.id,
            export_type="court_defense",
            requested_by_user_id=test_user.id,
            options_json={"profile_id": "court_defense_v1", "include_media": False},
            status="failed",
            progress_stage="packaging_evidence",
            error_message="zip failed",
        )
        db_session.add(failed)
        db_session.commit()
        db_session.refresh(failed)

        resp = client.post(
            f"/exports/{failed.export_id}/retry", json={}, headers=auth_headers
        )
        assert resp.status_code == 201
        payload = resp.json()
        assert payload["status"] == "queued"
        assert payload["incident_id"] == str(incident.incident_id)

        created = (
            db_session.query(Export)
            .filter(Export.export_id == uuid.UUID(payload["export_id"]))
            .first()
        )
        assert created is not None
        assert created.retry_parent_export_id == failed.export_id
        assert created.export_type == failed.export_type
        assert created.options_json == failed.options_json
        refreshed_failed = (
            db_session.query(Export)
            .filter(Export.export_id == failed.export_id)
            .first()
        )
        assert refreshed_failed.status == "failed"
        retry_event = (
            db_session.query(Event)
            .filter(Event.event_type == "export_retry_requested")
            .order_by(Event.created_at_utc.desc())
            .first()
        )
        assert retry_event is not None
        assert retry_event.payload["prior_export_id"] == str(failed.export_id)

        mock_gen.delay.assert_called_once_with(
            str(incident.incident_id),
            str(created.export_id),
            {"attempt_number": 2, "trigger": "retry_api"},
        )

    @patch("app.api.routes_exports.build_export")
    def test_retry_failed_export_accepts_overrides(
        self, mock_gen, client, db_session, test_org, auth_headers
    ):
        mock_gen.delay = MagicMock()
        incident = Incident(status="open", org_id=test_org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)
        failed = Export(
            incident_id=incident.incident_id,
            org_id=test_org.id,
            export_type="internal_review",
            options_json={},
            status="failed",
        )
        db_session.add(failed)
        db_session.commit()
        db_session.refresh(failed)

        resp = client.post(
            f"/exports/{failed.export_id}/retry",
            json={
                "export_type": "court_defense",
                "options_json": {"profile_id": "court_defense_v1"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        created = (
            db_session.query(Export)
            .filter(Export.export_id == uuid.UUID(resp.json()["export_id"]))
            .first()
        )
        assert created.export_type == "court_defense"
        assert created.options_json["profile_id"] == "court_defense_v1"
        assert created.options_json["include_media"] is True

    def test_retry_export_rejects_non_failed_and_preserves_ready_export(
        self, client, db_session, test_org, auth_headers
    ):
        incident = Incident(status="open", org_id=test_org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)
        ready = Export(
            incident_id=incident.incident_id,
            org_id=test_org.id,
            export_type="court_defense",
            options_json={"profile_id": "court_defense_v1"},
            status="ready",
            package_sha256="abc123",
        )
        db_session.add(ready)
        db_session.commit()
        db_session.refresh(ready)

        resp = client.post(
            f"/exports/{ready.export_id}/retry", json={}, headers=auth_headers
        )
        assert resp.status_code == 409
        db_session.refresh(ready)
        assert ready.status == "ready"
        assert ready.package_sha256 == "abc123"


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

        exp = Export(
            incident_id=inc.incident_id, org_id=test_org.id, status="requested"
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 409

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_ready(
        self,
        mock_generate_presigned_download_url,
        client,
        db_session,
        test_org,
        auth_headers,
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
        self,
        mock_generate_presigned_download_url,
        client,
        db_session,
        test_org,
        auth_headers,
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

        mock_generate_presigned_download_url.return_value = (
            "https://signed.example.com/k"
        )

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
        self,
        mock_generate_presigned_download_url,
        client,
        db_session,
        auth_headers,
        test_org,
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
        self,
        mock_generate_presigned_download_url,
        client,
        db_session,
        test_org,
        auth_headers,
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
        detail = resp.json()["detail"]
        assert detail["code"] == "THIRD_PARTY_DEGRADED"
        assert detail["message"] == "Export download is temporarily unavailable."
        assert detail.get("correlation_id")

    @patch("app.api.routes_exports.generate_presigned_download_url")
    def test_download_export_presign_failure_returns_502(
        self,
        mock_generate_presigned_download_url,
        client,
        db_session,
        test_org,
        auth_headers,
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
        detail = resp.json()["detail"]
        assert detail["code"] == "THIRD_PARTY_DEGRADED"
        assert detail["message"] == "Unable to prepare export download right now."
        assert detail.get("correlation_id")

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
        detail = resp.json()["detail"]
        assert detail["code"] == "EXPORT_EXPIRED"
        assert detail["message"] == "This export link has expired."
        assert detail.get("correlation_id")

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
        self,
        mock_generate_presigned_download_url,
        client,
        db_session,
        test_org,
        auth_headers,
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
        detail = resp.json()["detail"]
        assert detail["code"] == "THIRD_PARTY_DEGRADED"
        assert detail["message"] == "Unable to prepare export download right now."
        assert detail.get("correlation_id")


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

    def test_get_export_forbidden_for_other_org(self, client, db_session, auth_headers):
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

        status_resp = client.get(
            f"/exports/{exp.export_id}/status", headers=auth_headers
        )
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

        status_resp = client.get(
            f"/exports/{exp.export_id}/status", headers=auth_headers
        )
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


class TestVehicleImportJobs:
    def test_create_vehicle_import_job_and_read_results(
        self, client, db_session, test_org, auth_headers
    ):
        db_session.add(
            VehicleQrToken(
                qr_token="qr-token-1",
                org_id=test_org.id,
                adc_vehicle_id="UNIT-001",
                status="active",
            )
        )
        db_session.add(
            ExternalMapping(
                org_id=test_org.id,
                provider="samsara",
                domain="fleet",
                internal_entity_type="vehicle",
                internal_entity_id="unit-001",
                external_reference="provider-veh-1",
                status="active",
            )
        )
        db_session.commit()

        csv_content = (
            "unitNumber,vin,providerVehicleId,status\n"
            "UNIT-001,1HGBH41JXMN109186,provider-veh-1,active\n"
            "UNIT-002,1HGBH41JXMN109186,provider-veh-2,inactive\n"
            "UNIT-002,2HGBH41JXMN109187,provider-veh-3,active\n"
            ",2HGBH41JXMN109188,provider-veh-4,active\n"
        )

        create_resp = client.post(
            "/org/vehicles/import",
            headers=auth_headers,
            json={
                "provider": "samsara",
                "csv_content": csv_content,
                "header_mapping": {"unit_number": "unitNumber"},
                "inactive_unit_numbers": ["UNIT-002"],
            },
        )
        assert create_resp.status_code == 202
        job_id = create_resp.json()["job_id"]

        read_resp = client.get(
            f"/org/vehicles/import-jobs/{job_id}", headers=auth_headers
        )
        assert read_resp.status_code == 200
        payload = read_resp.json()
        assert payload["status"] == "failed"
        assert payload["records_total"] == 2
        assert payload["records_processed"] == 2
        assert payload["records_imported"] == 2
        assert payload["records_updated"] == 0
        assert payload["records_skipped"] == 1
        assert payload["records_errored"] == 2
        assert payload["summary"]["missing_qr_count"] == 1
        assert payload["summary"]["missing_provider_mapping_count"] == 1
        assert payload["summary"]["duplicate_like_count"] == 2
        assert payload["summary"]["inactive_count"] == 1
        assert any("VIN" in warning for warning in payload["warnings"])
        assert any(
            "duplicate unitNumber" in row for row in payload["outcomes"]["errored"]
        )
        assert any(
            "unitNumber is required" in row for row in payload["outcomes"]["errored"]
        )

        vehicles = (
            db_session.query(OrgVehicleRegistry)
            .filter(OrgVehicleRegistry.org_id == test_org.id)
            .all()
        )
        assert len(vehicles) == 2
        unit_two = next(item for item in vehicles if item.unit_number == "UNIT-002")
        assert unit_two.is_active is False

    def test_get_vehicle_import_job_not_found(self, client, auth_headers):
        resp = client.get(
            f"/org/vehicles/import-jobs/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404


class TestDriverImportJobs:
    def test_create_driver_import_job_and_read_results(
        self, client, db_session, test_org, auth_headers
    ):
        existing = Driver(
            org_id=test_org.id,
            phone_e164="+15550001111",
            display_name="Existing Driver",
            is_active=True,
        )
        db_session.add(existing)
        db_session.commit()
        db_session.refresh(existing)
        db_session.add(
            DriverVehicleAssignment(
                org_id=test_org.id,
                driver_id=existing.driver_id,
                adc_vehicle_id="UNIT-001",
                source="manual",
            )
        )
        db_session.add(
            ExternalMapping(
                org_id=test_org.id,
                provider="samsara",
                domain="fleet",
                internal_entity_type="driver",
                internal_entity_id=str(existing.driver_id),
                external_reference="provider-driver-1",
                status="active",
            )
        )
        db_session.commit()

        csv_content = (
            "firstName,lastName,mobile,status\n"
            "Alice,Example,(555) 000-1111,active\n"
            "Bob,Builder,invalid-phone,active\n"
            "Chris,Driver,5550002222,inactive\n"
            "Dana,Dupe,5550002222,active\n"
            ",NoFirst,5550003333,active\n"
            "NoLast,,5550004444,active\n"
        )

        create_resp = client.post(
            "/org/drivers/import",
            headers=auth_headers,
            json={
                "provider": "samsara",
                "csv_content": csv_content,
                "header_mapping": {"phone": "mobile"},
                "inactive_mobile_phones": ["5550002222"],
            },
        )
        assert create_resp.status_code == 202
        job_id = create_resp.json()["job_id"]

        read_resp = client.get(
            f"/org/drivers/import-jobs/{job_id}", headers=auth_headers
        )
        assert read_resp.status_code == 200
        payload = read_resp.json()
        assert payload["status"] == "failed"
        assert payload["records_total"] == 2
        assert payload["records_processed"] == 2
        assert payload["records_imported"] == 1
        assert payload["records_updated"] == 1
        assert payload["records_skipped"] == 1
        assert payload["records_errored"] == 4
        assert payload["summary"]["invalid_phone_count"] == 1
        assert payload["summary"]["duplicate_warning_count"] == 1
        assert payload["summary"]["missing_assignment_count"] == 1
        assert payload["summary"]["missing_external_mapping_count"] == 1
        assert payload["summary"]["needs_review_count"] == 3
        assert payload["summary"]["inactive_count"] == 1
        assert len(payload["outcomes"]["invalid_phone"]) == 1
        assert len(payload["outcomes"]["duplicate_warning"]) == 1
        assert len(payload["outcomes"]["missing_assignment_or_mapping"]) == 1
        assert len(payload["outcomes"]["needs_review"]) == 3
        assert any(
            "firstName is required" in row for row in payload["outcomes"]["errored"]
        )
        assert any(
            "lastName is required" in row for row in payload["outcomes"]["errored"]
        )
        assert any(
            "missing assignment, external_mapping" in row for row in payload["warnings"]
        )

        drivers = db_session.query(Driver).filter(Driver.org_id == test_org.id).all()
        assert len(drivers) == 2
        imported = next(row for row in drivers if row.phone_e164 == "+15550002222")
        assert imported.display_name == "Chris Driver"
        assert imported.is_active is False

    def test_get_driver_import_job_not_found(self, client, auth_headers):
        resp = client.get(
            f"/org/drivers/import-jobs/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404


# ── Health check ────────────────────────────────────────────────────


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
