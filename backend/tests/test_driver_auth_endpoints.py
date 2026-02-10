"""Tests for driver auth endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    request_resp = client.post(
        "/driver/auth/request-otp",
        json={"phone_e164": phone_e164},
    )
    assert request_resp.status_code == 200
    assert request_resp.json()["detail"] == "OTP sent"

    challenge = db_session.query(OtpChallenge).filter_by(phone_e164=phone_e164).first()
    assert challenge is not None

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
