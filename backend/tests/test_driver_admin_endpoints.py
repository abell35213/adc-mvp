"""Tests for driver and admin endpoints."""

import hashlib
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    Driver,
    DriverInstructionSet,
    DriverInstructionStep,
    DriverVehicleAssignment,
    Event,
    Incident,
    Org,
    User,
    UserOrg,
    VehicleQrToken,
)
from app.db.session import get_db
from app.core.security import hash_password, create_access_token
from app.main import app


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_session():
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
def admin_user(db_session, test_org):
    user = User(
        email="admin@example.com",
        password_hash=hash_password("adminpass"),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    link = UserOrg(user_id=user.id, org_id=test_org.id)
    db_session.add(link)
    db_session.commit()
    return user


@pytest.fixture()
def admin_headers(admin_user):
    token = create_access_token({"sub": str(admin_user.id), "role": admin_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def non_admin_user(db_session, test_org):
    user = User(
        email="user@example.com",
        password_hash=hash_password("userpass"),
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
def non_admin_headers(non_admin_user):
    token = create_access_token({"sub": str(non_admin_user.id), "role": non_admin_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def test_driver(db_session, test_org):
    driver = Driver(
        org_id=test_org.id,
        phone_e164="+15551234567",
        display_name="Test Driver",
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)
    return driver


@pytest.fixture()
def test_assignment(db_session, test_org, test_driver):
    assignment = DriverVehicleAssignment(
        org_id=test_org.id,
        driver_id=test_driver.driver_id,
        adc_vehicle_id="veh-100",
        source="manual",
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)
    return assignment


@pytest.fixture()
def active_qr_token(db_session, test_org):
    token = VehicleQrToken(
        qr_token="test-token-abc123",
        org_id=test_org.id,
        adc_vehicle_id="veh-200",
        status="active",
    )
    db_session.add(token)
    db_session.commit()
    return token


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


# ── GET /driver/me ──────────────────────────────────────────────────


class TestDriverMe:
    def test_driver_me_returns_profile_with_vehicle(
        self, client, test_driver, test_assignment
    ):
        resp = client.get("/driver/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["driver_id"] == str(test_driver.driver_id)
        assert data["display_name"] == "Test Driver"
        assert data["phone_e164"] == "+15551234567"
        assert data["vehicle"] is not None
        assert data["vehicle"]["adc_vehicle_id"] == "veh-100"

    def test_driver_me_returns_null_vehicle_when_no_assignment(
        self, client, test_driver
    ):
        resp = client.get("/driver/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle"] is None

    def test_driver_me_returns_401_when_no_driver(self, client):
        resp = client.get("/driver/me")
        assert resp.status_code == 401


# ── POST /driver/vehicle/resolve-qr ────────────────────────────────


class TestResolveQr:
    def test_resolve_qr_returns_vehicle(self, client, active_qr_token):
        resp = client.post(
            "/driver/vehicle/resolve-qr",
            json={"qr_token": "test-token-abc123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adc_vehicle_id"] == "veh-200"
        assert "display_label" in data

    def test_resolve_qr_emits_event(self, client, db_session, active_qr_token):
        client.post(
            "/driver/vehicle/resolve-qr",
            json={"qr_token": "test-token-abc123"},
        )
        events = db_session.query(Event).filter(
            Event.event_type == "driver_vehicle_resolved"
        ).all()
        assert len(events) == 1
        payload = events[0].payload
        expected_hash = hashlib.sha256(b"test-token-abc123").hexdigest()
        assert payload["token_sha256"] == expected_hash
        assert payload["adc_vehicle_id"] == "veh-200"

    def test_resolve_qr_stores_hash_not_raw_token(
        self, client, db_session, active_qr_token
    ):
        client.post(
            "/driver/vehicle/resolve-qr",
            json={"qr_token": "test-token-abc123"},
        )
        events = db_session.query(Event).filter(
            Event.event_type == "driver_vehicle_resolved"
        ).all()
        assert len(events) == 1
        payload = events[0].payload
        # Must NOT contain the raw token
        assert "test-token-abc123" not in str(payload)

    def test_resolve_qr_inactive_token_returns_404(self, client, db_session, test_org):
        revoked = VehicleQrToken(
            qr_token="revoked-token",
            org_id=test_org.id,
            adc_vehicle_id="veh-300",
            status="revoked",
        )
        db_session.add(revoked)
        db_session.commit()
        resp = client.post(
            "/driver/vehicle/resolve-qr",
            json={"qr_token": "revoked-token"},
        )
        assert resp.status_code == 404

    def test_resolve_qr_unknown_token_returns_404(self, client):
        resp = client.post(
            "/driver/vehicle/resolve-qr",
            json={"qr_token": "nonexistent-token"},
        )
        assert resp.status_code == 404


# ── POST /admin/vehicles/{vehicle_id}/qr/rotate ────────────────────


class TestRotateQr:
    def test_rotate_creates_new_token(self, client, admin_headers):
        resp = client.post(
            "/admin/vehicles/veh-500/qr/rotate",
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "qr_token" in data
        assert len(data["qr_token"]) > 20  # base64url encoded 32 bytes

    def test_rotate_revokes_existing_active_token(
        self, client, db_session, test_org, admin_headers
    ):
        old = VehicleQrToken(
            qr_token="old-token",
            org_id=test_org.id,
            adc_vehicle_id="veh-600",
            status="active",
        )
        db_session.add(old)
        db_session.commit()

        resp = client.post(
            "/admin/vehicles/veh-600/qr/rotate",
            headers=admin_headers,
        )
        assert resp.status_code == 201

        db_session.refresh(old)
        assert old.status == "rotated"

    def test_rotate_emits_event(self, client, db_session, admin_headers):
        client.post(
            "/admin/vehicles/veh-700/qr/rotate",
            headers=admin_headers,
        )
        events = db_session.query(Event).filter(
            Event.event_type == "vehicle_qr_rotated"
        ).all()
        assert len(events) == 1
        assert events[0].payload["adc_vehicle_id"] == "veh-700"
        assert "new_token_sha256" in events[0].payload

    def test_rotate_requires_admin_role(self, client, non_admin_headers):
        resp = client.post(
            "/admin/vehicles/veh-800/qr/rotate",
            headers=non_admin_headers,
        )
        assert resp.status_code == 403

    def test_rotate_no_auth_returns_401(self, client):
        resp = client.post("/admin/vehicles/veh-800/qr/rotate")
        assert resp.status_code in (401, 403)


# ── POST /driver/incidents/initiate ─────────────────────────────────


class TestDriverInitiate:
    @patch("app.api.routes_driver.notify_safety")
    @patch("app.api.routes_driver.capture_telematics_bundle")
    @patch("app.api.routes_driver.capture_dashcam")
    def test_driver_initiate_creates_incident_and_events(
        self,
        mock_dash,
        mock_tele,
        mock_notify,
        client,
        db_session,
        test_driver,
        test_assignment,
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()
        mock_notify.delay = MagicMock()

        resp = client.post(
            "/driver/incidents/initiate",
            json={"vehicle_strategy": "last_assigned"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["safety_notified"] is True
        assert data["capture_started"] is True

        incident = db_session.query(Incident).first()
        assert incident is not None
        assert incident.adc_vehicle_id == "veh-100"

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id
        ).all()
        event_types = {event.event_type for event in events}
        assert "incident_protocol_initiated" in event_types
        assert "evidence_lockdown_started" in event_types

    @patch("app.api.routes_driver.notify_safety")
    @patch("app.api.routes_driver.capture_telematics_bundle")
    @patch("app.api.routes_driver.capture_dashcam")
    def test_driver_initiate_resolves_vehicle_by_qr(
        self,
        mock_dash,
        mock_tele,
        mock_notify,
        client,
        db_session,
        test_driver,
        active_qr_token,
    ):
        mock_dash.delay = MagicMock()
        mock_tele.delay = MagicMock()
        mock_notify.delay = MagicMock()

        resp = client.post(
            "/driver/incidents/initiate",
            json={"vehicle_strategy": "qr", "qr_token": "test-token-abc123"},
        )
        assert resp.status_code == 200
        incident = db_session.query(Incident).first()
        assert incident.adc_vehicle_id == "veh-200"


# ── GET /driver/instructions/active ─────────────────────────────────


def seed_instruction_set(db_session, org_id, scope, require_ack=False):
    instruction_set = DriverInstructionSet(
        org_id=org_id, scope=scope, require_ack=require_ack
    )
    db_session.add(instruction_set)
    db_session.commit()
    step = DriverInstructionStep(
        instruction_set_id=instruction_set.instruction_set_id,
        step_order=1,
        title=f"{scope} step",
        body="Do the thing.",
    )
    db_session.add(step)
    db_session.commit()
    return instruction_set


class TestDriverInstructions:
    def test_active_instructions_prefers_company(
        self, client, db_session, test_org, test_driver
    ):
        seed_instruction_set(db_session, test_org.id, "default")
        company_set = seed_instruction_set(db_session, test_org.id, "company")

        resp = client.get("/driver/instructions/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instruction_set_id"] == str(company_set.instruction_set_id)
        assert data["scope"] == "company"

    def test_active_instructions_prefers_insurer_over_default(
        self, client, db_session, test_org, test_driver
    ):
        seed_instruction_set(db_session, test_org.id, "default")
        insurer_set = seed_instruction_set(db_session, test_org.id, "insurer")

        resp = client.get("/driver/instructions/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instruction_set_id"] == str(insurer_set.instruction_set_id)
        assert data["scope"] == "insurer"

    def test_active_instructions_falls_back_to_default(
        self, client, db_session, test_org, test_driver
    ):
        default_set = seed_instruction_set(db_session, test_org.id, "default")

        resp = client.get("/driver/instructions/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instruction_set_id"] == str(default_set.instruction_set_id)
        assert data["scope"] == "default"


# ── POST /driver/instructions/ack ───────────────────────────────────


class TestDriverInstructionAck:
    def test_ack_writes_event(
        self, client, db_session, test_org, test_driver
    ):
        instruction_set = seed_instruction_set(
            db_session, test_org.id, "default", require_ack=True
        )

        resp = client.post(
            "/driver/instructions/ack",
            json={"instruction_set_id": str(instruction_set.instruction_set_id)},
        )
        assert resp.status_code == 200

        events = db_session.query(Event).filter(
            Event.event_type == "driver_instruction_acknowledged"
        ).all()
        assert len(events) == 1
        assert (
            events[0].payload["instruction_set_id"]
            == str(instruction_set.instruction_set_id)
        )


# ── GET /admin/vehicles/{vehicle_id}/qr ─────────────────────────────


class TestGetQrPayload:
    def test_returns_deep_link(self, client, admin_headers):
        resp = client.get(
            "/admin/vehicles/veh-900/qr",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deep_link"] == "adc://vehicle/veh-900"

    def test_requires_admin_role(self, client, non_admin_headers):
        resp = client.get(
            "/admin/vehicles/veh-900/qr",
            headers=non_admin_headers,
        )
        assert resp.status_code == 403

    def test_no_auth_returns_401(self, client):
        resp = client.get("/admin/vehicles/veh-900/qr")
        assert resp.status_code in (401, 403)
