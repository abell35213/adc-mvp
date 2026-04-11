"""Tests for driver auth OTP endpoints."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_driver_auth
from app.db.models import Base, Driver, MessageOperation, Org, OtpChallenge
from app.db.session import get_db
from app.main import app
from tests.helpers.fake_redis import FakeRedisRateLimiter


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


@pytest.fixture(autouse=True)
def reset_rate_limits():
    routes_driver_auth._redis_client = FakeRedisRateLimiter()
    routes_driver_auth._rate_limit_script_sha = None
    yield
    routes_driver_auth._redis_client = None
    routes_driver_auth._rate_limit_script_sha = None


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
        otp_request_operation = (
            db_session.query(MessageOperation)
            .filter(
                MessageOperation.purpose == "otp_request",
                MessageOperation.to_e164 == driver.phone_e164,
            )
            .first()
        )
        assert otp_request_operation is not None
        assert otp_request_operation.status == "sent"
        assert otp_request_operation.provider_message_id == "VE123"

        verify_resp = client.post(
            "/driver/auth/verify-otp",
            json={"phone_e164": driver.phone_e164, "otp_code": "123456"},
        )
        assert verify_resp.status_code == 200
        token = verify_resp.json()["access_token"]
        assert token
        otp_verify_operation = (
            db_session.query(MessageOperation)
            .filter(MessageOperation.purpose == "otp_verify")
            .order_by(MessageOperation.created_at_utc.desc())
            .first()
        )
        assert otp_verify_operation is not None
        assert otp_verify_operation.status == "delivered"

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


def _create_challenge(
    db_session,
    phone_e164: str,
    *,
    status: str = "pending",
    attempt_count: int = 0,
    created_at_utc: datetime | None = None,
    expires_at_utc: datetime | None = None,
):
    challenge = OtpChallenge(
        phone_e164=phone_e164,
        otp_code_hash="",
        status=status,
        attempt_count=attempt_count,
        created_at_utc=created_at_utc or datetime.now(timezone.utc),
        expires_at_utc=expires_at_utc
        or (datetime.now(timezone.utc) + timedelta(minutes=5)),
    )
    db_session.add(challenge)
    db_session.commit()
    db_session.refresh(challenge)
    return challenge


def test_verify_otp_latest_locked_challenge_returns_423(client, db_session, driver):
    now = datetime.now(timezone.utc)
    _create_challenge(
        db_session,
        driver.phone_e164,
        status="pending",
        created_at_utc=now - timedelta(minutes=1),
        expires_at_utc=now + timedelta(minutes=5),
    )
    _create_challenge(
        db_session,
        driver.phone_e164,
        status="locked",
        created_at_utc=now,
        expires_at_utc=now + timedelta(minutes=5),
    )

    verify_resp = client.post(
        "/driver/auth/verify-otp",
        json={"phone_e164": driver.phone_e164, "otp_code": "123456"},
    )

    assert verify_resp.status_code == 423
    assert verify_resp.json()["detail"] == "Challenge locked due to too many attempts"


def test_verify_otp_latest_verified_challenge_returns_400(client, db_session, driver):
    now = datetime.now(timezone.utc)
    _create_challenge(
        db_session,
        driver.phone_e164,
        status="pending",
        created_at_utc=now - timedelta(minutes=1),
        expires_at_utc=now + timedelta(minutes=5),
    )
    _create_challenge(
        db_session,
        driver.phone_e164,
        status="verified",
        created_at_utc=now,
        expires_at_utc=now + timedelta(minutes=5),
    )

    verify_resp = client.post(
        "/driver/auth/verify-otp",
        json={"phone_e164": driver.phone_e164, "otp_code": "123456"},
    )

    assert verify_resp.status_code == 400
    assert verify_resp.json()["detail"] == "Challenge already verified"


def test_verify_otp_latest_expired_challenge_returns_410(client, db_session, driver):
    now = datetime.now(timezone.utc)
    _create_challenge(
        db_session,
        driver.phone_e164,
        status="pending",
        created_at_utc=now - timedelta(minutes=1),
        expires_at_utc=now + timedelta(minutes=5),
    )
    _create_challenge(
        db_session,
        driver.phone_e164,
        status="expired",
        created_at_utc=now,
        expires_at_utc=now - timedelta(minutes=1),
    )

    verify_resp = client.post(
        "/driver/auth/verify-otp",
        json={"phone_e164": driver.phone_e164, "otp_code": "123456"},
    )

    assert verify_resp.status_code == 410
    assert verify_resp.json()["detail"] == "Challenge expired"


def test_verify_otp_invalid_code_increments_attempts_and_locks(client, db_session, driver):
    challenge = _create_challenge(
        db_session,
        driver.phone_e164,
        status="pending",
        attempt_count=4,
        expires_at_utc=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    with patch("app.services.twilio_verify.check_verification", return_value=False):
        verify_resp = client.post(
            "/driver/auth/verify-otp",
            json={"phone_e164": driver.phone_e164, "otp_code": "000000"},
        )

    db_session.refresh(challenge)
    assert verify_resp.status_code == 423
    assert verify_resp.json()["detail"] == "Challenge locked due to too many attempts"
    assert challenge.attempt_count == 5
    assert challenge.status == "locked"
