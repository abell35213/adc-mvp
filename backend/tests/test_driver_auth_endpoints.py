"""Tests for driver auth OTP endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_driver_auth
from app.db.models import Base, Driver, Org, OtpChallenge
from app.db.session import get_db
from app.main import app


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


@pytest.fixture()
def driver(db_session):
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    row = Driver(
        org_id=org.id,
        phone_e164="+15551234567",
        display_name="Driver One",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_driver_otp_flow(client, db_session, driver):
    with (
        patch(
            "app.services.twilio_verify.start_verification",
            return_value="VE123",
        ),
        patch("app.services.twilio_verify.check_verification", return_value=True),
    ):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": driver.phone_e164},
        )
        assert request_resp.status_code == 200
        assert request_resp.json()["detail"] == "OTP sent"

        challenge = (
            db_session.query(OtpChallenge)
            .filter_by(phone_e164=driver.phone_e164)
            .order_by(OtpChallenge.created_at_utc.desc())
            .first()
        )
        assert challenge is not None
        assert challenge.twilio_sid == "VE123"

        verify_resp = client.post(
            "/driver/auth/verify-otp",
            json={"phone_e164": driver.phone_e164, "otp_code": "123456"},
        )
        assert verify_resp.status_code == 200
        token = verify_resp.json()["access_token"]
        assert token

        me_resp = client.get(
            "/driver/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["phone_e164"] == driver.phone_e164


def test_driver_otp_rejects_invalid_code(client, driver):
    with (
        patch("app.services.twilio_verify.start_verification", return_value="VE123"),
        patch("app.services.twilio_verify.check_verification", return_value=False),
    ):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": driver.phone_e164},
        )
        assert request_resp.status_code == 200

        verify_resp = client.post(
            "/driver/auth/verify-otp",
            json={"phone_e164": driver.phone_e164, "otp_code": "000000"},
        )
        assert verify_resp.status_code == 401


def test_driver_request_otp_rate_limited(client, driver):
    routes_driver_auth._request_timestamps.clear()
    with patch("app.services.twilio_verify.start_verification", return_value="VE123"):
        for _ in range(routes_driver_auth._REQUEST_LIMIT):
            response = client.post(
                "/driver/auth/request-otp",
                json={"phone_e164": driver.phone_e164},
            )
            assert response.status_code == 200

        blocked = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": driver.phone_e164},
        )
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
