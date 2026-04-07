"""Contract tests ensuring backend JSON matches frontend/lib/api.ts expectations."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import Base, Org, User, UserOrg
from app.db.session import get_db
from app.main import app


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
    org = Org(name="Contract Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def test_user(db_session, test_org):
    user = User(
        email="contracts@example.com",
        password_hash=hash_password("supersecure"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
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


def _assert_uuid(value: str):
    assert isinstance(value, str)
    uuid.UUID(value)


def _assert_iso_datetime(value: str):
    assert isinstance(value, str)
    normalized = value.replace("Z", "+00:00")
    datetime.fromisoformat(normalized)


@patch("app.api.routes_incidents.capture_telematics_bundle")
@patch("app.api.routes_incidents.capture_dashcam")
def test_incident_list_contract_matches_frontend(
    mock_dash,
    mock_tele,
    client: TestClient,
    auth_headers: dict[str, str],
):
    mock_dash.delay = MagicMock()
    mock_tele.delay = MagicMock()

    create_resp = client.post(
        "/incidents/",
        json={
            "severity": "serious",
            "adc_vehicle_id": "veh-123",
            "samsara_vehicle_id": "sm-456",
            "adc_driver_id": "drv-789",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    resp = client.get("/incidents/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body

    item = body[0]
    # Required frontend Incident fields.
    for field in (
        "incident_id",
        "status",
        "severity",
        "adc_vehicle_id",
        "samsara_vehicle_id",
        "adc_driver_id",
    ):
        assert field in item

    _assert_uuid(item["incident_id"])
    assert isinstance(item["status"], str)
    assert item["severity"] in {"minor", "serious", "critical", None}
    assert isinstance(item["adc_vehicle_id"], str) or item["adc_vehicle_id"] is None
    assert isinstance(item["samsara_vehicle_id"], str) or item["samsara_vehicle_id"] is None
    assert isinstance(item["adc_driver_id"], str) or item["adc_driver_id"] is None

    if item.get("created_at_utc"):
        _assert_iso_datetime(item["created_at_utc"])
    if "evidence_captured" in item:
        assert isinstance(item["evidence_captured"], int)
    if "evidence_total" in item:
        assert isinstance(item["evidence_total"], int)


@patch("app.api.routes_incidents.capture_telematics_bundle")
@patch("app.api.routes_incidents.capture_dashcam")
def test_incident_detail_contract_matches_frontend(
    mock_dash,
    mock_tele,
    client: TestClient,
    auth_headers: dict[str, str],
):
    mock_dash.delay = MagicMock()
    mock_tele.delay = MagicMock()

    create_resp = client.post(
        "/incidents/",
        json={
            "severity": "minor",
            "adc_vehicle_id": "veh-abc",
            "samsara_vehicle_id": "sm-def",
            "adc_driver_id": "drv-ghi",
        },
        headers=auth_headers,
    )
    incident_id = create_resp.json()["incident_id"]

    detail_resp = client.get(f"/incidents/{incident_id}", headers=auth_headers)
    assert detail_resp.status_code == 200

    detail = detail_resp.json()
    for field in (
        "incident_id",
        "status",
        "severity",
        "adc_vehicle_id",
        "samsara_vehicle_id",
        "adc_driver_id",
        "evidence_inventory",
        "export_status",
        "timeline",
    ):
        assert field in detail

    _assert_uuid(detail["incident_id"])
    assert isinstance(detail["evidence_inventory"], list)
    assert isinstance(detail["export_status"], list)
    assert isinstance(detail["timeline"], list)


@patch("app.api.routes_exports.build_export")
@patch("app.api.routes_incidents.capture_telematics_bundle")
@patch("app.api.routes_incidents.capture_dashcam")
def test_export_response_contract_matches_frontend(
    mock_dash,
    mock_tele,
    mock_build_export,
    client: TestClient,
    auth_headers: dict[str, str],
):
    mock_dash.delay = MagicMock()
    mock_tele.delay = MagicMock()
    mock_build_export.delay = MagicMock()

    create_resp = client.post(
        "/incidents/",
        json={
            "severity": "critical",
            "adc_vehicle_id": "veh-z9",
            "samsara_vehicle_id": "sm-z9",
            "adc_driver_id": "drv-z9",
        },
        headers=auth_headers,
    )
    incident_id = create_resp.json()["incident_id"]

    export_resp = client.post(
        "/exports/",
        json={"incident_id": incident_id, "export_type": "court_defense"},
        headers=auth_headers,
    )
    assert export_resp.status_code == 201
    payload = export_resp.json()

    for field in ("export_id", "incident_id", "export_type", "status", "created_at_utc"):
        assert field in payload
    _assert_uuid(payload["export_id"])
    _assert_uuid(payload["incident_id"])
    assert payload["export_type"] == "court_defense"
    assert payload["status"] in {"requested", "queued", "processing", "ready", "failed", "expired"}
    assert isinstance(payload["created_at_utc"], str)
