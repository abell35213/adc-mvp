"""Tests for driver auth endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_driver_auth import router as driver_auth_router
from app.core.security import decode_access_token
from app.db.models import Base, Driver, Org, OtpChallenge
from app.db.session import get_db
from app.services.phone_normalize import normalize_phone

app = FastAPI()
app.include_router(driver_auth_router, prefix="/driver/auth")


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


def _create_driver(db_session, phone_e164: str) -> Driver:
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    driver = Driver(org_id=org.id, phone_e164=phone_e164, display_name=phone_e164)
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)
    return driver


def test_driver_otp_flow(client, db_session):
    raw_phone = "(555) 123-4567"
    phone_e164 = normalize_phone(raw_phone)
    verify_phone = "5551234567"
    assert normalize_phone(verify_phone) == phone_e164
    driver = _create_driver(db_session, phone_e164)

    with (
        patch("app.services.twilio_verify.start_verification", return_value="sid-123"),
        patch("app.services.twilio_verify.check_verification", return_value=True),
    ):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": raw_phone},
        )
        assert request_resp.status_code == 200
        assert request_resp.json()["detail"] == "OTP sent"

        challenge = (
            db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
        )
        assert challenge is not None
        assert challenge.twilio_sid == "sid-123"

        verify_resp = client.post(
            "/driver/auth/verify-otp",
            json={"phone_e164": verify_phone, "otp_code": "123456"},
        )
        assert verify_resp.status_code == 200
        token = verify_resp.json()["access_token"]
        assert token

        payload = decode_access_token(token)
        assert payload["sub"] == str(driver.driver_id)
        assert payload["scope"] == "driver"
        assert payload["phone"] == phone_e164


def test_driver_otp_rejects_invalid_code(client, db_session):
    phone_e164 = normalize_phone("5551230000")
    _create_driver(db_session, phone_e164)

    with (
        patch("app.services.twilio_verify.start_verification", return_value="sid-456"),
        patch("app.services.twilio_verify.check_verification", return_value=False),
    ):
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
        challenge = (
            db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
        )
        assert challenge.attempt_count == 1


def test_driver_otp_expires(client, db_session):
    phone_e164 = normalize_phone("5550001111")
    _create_driver(db_session, phone_e164)

    with patch("app.services.twilio_verify.start_verification", return_value="sid-789"):
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
    assert verify_resp.status_code == 410


def test_driver_otp_request_handles_twilio_failure(client, db_session):
    phone_e164 = normalize_phone("5559990000")
    with patch(
        "app.services.twilio_verify.start_verification",
        side_effect=Exception("Twilio down"),
    ):
        request_resp = client.post(
            "/driver/auth/request-otp",
            json={"phone_e164": phone_e164},
        )
        assert request_resp.status_code == 200

    challenge = db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
    assert challenge is not None
    assert challenge.twilio_sid is None
