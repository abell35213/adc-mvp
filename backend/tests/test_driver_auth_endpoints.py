"""Tests for driver auth endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_driver import _generate_otp_code, _hash_otp_code
from app.db.models import Base, Driver, OtpChallenge
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


def test_driver_otp_flow(client, db_session):
    phone_e164 = "+15551234567"
    with patch("app.api.routes_driver._generate_otp_code", return_value="123456"):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": phone_e164},
        )
        assert request_resp.status_code == 200
        assert request_resp.json()["detail"] == "OTP sent"

        challenge = (
            db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
        )
        assert challenge is not None
        assert challenge.otp_code_hash == _hash_otp_code("123456")

        verify_resp = client.post(
            "/driver/auth/verify-otp",
            json={"phone_e164": phone_e164, "otp_code": "123456"},
        )
        assert verify_resp.status_code == 200
        token = verify_resp.json()["access_token"]
        assert token

        me_resp = client.get(
            "/driver/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["phone_e164"] == phone_e164
        assert data["driver_id"] == str(
            db_session.query(Driver).filter_by(phone_e164=phone_e164).first().driver_id
        )


def test_driver_otp_rejects_invalid_code(client, db_session):
    phone_e164 = "+15551230000"
    with patch("app.api.routes_driver._generate_otp_code", return_value="123456"):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": phone_e164},
        )
        assert request_resp.status_code == 200

    verify_resp = client.post(
        "/driver/auth/verify-otp",
        json={"phone_e164": phone_e164, "otp_code": "000000"},
    )
    assert verify_resp.status_code == 401
    challenge = db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
    assert challenge.attempt_count == 1


def test_driver_otp_expires(client, db_session):
    phone_e164 = "+15550001111"
    with patch("app.api.routes_driver._generate_otp_code", return_value="123456"):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": phone_e164},
        )
        assert request_resp.status_code == 200

    challenge = db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
    challenge.expires_at_utc = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    verify_resp = client.post(
        "/driver/auth/verify-otp",
        json={"phone_e164": phone_e164, "otp_code": "123456"},
    )
    assert verify_resp.status_code == 401


def test_generate_otp_code_format():
    with patch("app.api.routes_driver.secrets.randbelow", return_value=42):
        assert _generate_otp_code() == "000042"


def test_driver_otp_resend_cooldown(client):
    phone_e164 = "+15559990000"
    with patch("app.api.routes_driver._generate_otp_code", return_value="123456"):
        first_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": phone_e164},
        )
        assert first_resp.status_code == 200

        second_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": phone_e164},
        )
        assert second_resp.status_code == 429
        assert "Retry-After" in second_resp.headers
