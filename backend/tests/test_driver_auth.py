"""Tests for driver OTP authentication helpers and JWT guard."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.models import Base, Driver, Org, OtpChallenge
from app.db.session import get_db
from app.services.phone_normalize import normalize_phone


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
    """Create a test org for driver tests."""
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


# ── Phone normalisation ────────────────────────────────────────────


class TestPhoneNormalize:
    def test_ten_digit(self):
        assert normalize_phone("5551234567") == "+15551234567"

    def test_eleven_digit_with_country_code(self):
        assert normalize_phone("15551234567") == "+15551234567"

    def test_formatted_parentheses(self):
        assert normalize_phone("(555) 123-4567") == "+15551234567"

    def test_formatted_dashes(self):
        assert normalize_phone("555-123-4567") == "+15551234567"

    def test_with_plus_and_spaces(self):
        assert normalize_phone("+1 555 123 4567") == "+15551234567"

    def test_invalid_short(self):
        with pytest.raises(ValueError):
            normalize_phone("12345")

    def test_invalid_too_long(self):
        with pytest.raises(ValueError):
            normalize_phone("123456789012345")


# ── Repo layer ─────────────────────────────────────────────────────


class TestDriverRepo:
    def test_get_otp_challenge_uses_challenge_id(self, db_session):
        """get_otp_challenge must filter on challenge_id, not id."""
        from app.db.repo.drivers import get_otp_challenge, create_otp_challenge

        ch = create_otp_challenge(db_session, "+15551234567")
        found = get_otp_challenge(db_session, ch.challenge_id)
        assert found is not None
        assert found.challenge_id == ch.challenge_id

    def test_increment_otp_attempts_locks_at_max(self, db_session):
        """Attempts reach MAX_OTP_ATTEMPTS -> status becomes 'locked'."""
        from app.db.repo.drivers import create_otp_challenge, increment_otp_attempts

        ch = create_otp_challenge(db_session, "+15551234567")
        for _ in range(5):
            ch = increment_otp_attempts(db_session, ch)
        assert ch.status == "locked"
        assert ch.attempt_count == 5

    def test_mark_otp_verified(self, db_session):
        """mark_otp_verified sets status to 'verified'."""
        from app.db.repo.drivers import create_otp_challenge, mark_otp_verified

        ch = create_otp_challenge(db_session, "+15551234567")
        ch = mark_otp_verified(db_session, ch)
        assert ch.status == "verified"

    def test_find_or_create_driver_requires_org(self, db_session, test_org):
        """find_or_create_driver creates a driver with org_id and display_name."""
        from app.db.repo.drivers import find_or_create_driver

        driver = find_or_create_driver(
            db_session, "+15551234567", org_id=test_org.id, display_name="Test"
        )
        assert driver.driver_id is not None
        assert driver.org_id == test_org.id
        assert driver.display_name == "Test"

    def test_get_driver_by_id(self, db_session, test_org):
        """get_driver_by_id filters on driver_id column."""
        from app.db.repo.drivers import get_driver_by_id

        driver = Driver(
            phone_e164="+15551234567",
            org_id=test_org.id,
            display_name="Test",
        )
        db_session.add(driver)
        db_session.commit()
        db_session.refresh(driver)

        found = get_driver_by_id(db_session, driver.driver_id)
        assert found is not None
        assert found.driver_id == driver.driver_id


# ── Driver JWT guard ───────────────────────────────────────────────


class TestDriverJWTGuard:
    def test_driver_token_has_driver_scope(self, db_session, test_org):
        """Verify that tokens issued to drivers have scope=driver."""
        from app.core.security import decode_access_token

        driver = Driver(
            phone_e164="+15551234567",
            org_id=test_org.id,
            display_name="Test Driver",
        )
        db_session.add(driver)
        db_session.commit()
        db_session.refresh(driver)

        token = create_access_token({
            "sub": str(driver.driver_id),
            "scope": "driver",
            "phone": driver.phone_e164,
        })
        payload = decode_access_token(token)
        assert payload["scope"] == "driver"
        assert payload["sub"] == str(driver.driver_id)

    def test_get_current_driver_rejects_no_token(self, db_session):
        """The get_current_driver dependency rejects unauthenticated calls."""
        from app.core.deps import get_current_driver
        from fastapi import HTTPException

        request = MagicMock()
        request.cookies.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_driver(request=request, creds=None, db=db_session)
        assert exc_info.value.status_code == 401

    def test_get_current_driver_rejects_user_token(self, db_session):
        """A regular user token should not be accepted as a driver token."""
        from app.core.deps import get_current_driver
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        user_token = create_access_token({"sub": str(uuid.uuid4()), "role": "admin"})

        request = MagicMock()
        request.cookies.get.return_value = None
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=user_token)

        with pytest.raises(HTTPException) as exc_info:
            get_current_driver(request=request, creds=creds, db=db_session)
        assert exc_info.value.status_code == 403

    def test_get_current_driver_rejects_malformed_sub(self, db_session):
        """A driver token with a malformed sub should return 401, not 500."""
        from app.core.deps import get_current_driver
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token({"sub": "not-a-uuid", "scope": "driver"})

        request = MagicMock()
        request.cookies.get.return_value = None
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            get_current_driver(request=request, creds=creds, db=db_session)
        assert exc_info.value.status_code == 401

    def test_get_current_driver_accepts_valid_driver_token(self, db_session, test_org):
        """A valid driver token should be accepted."""
        from app.core.deps import get_current_driver
        from fastapi.security import HTTPAuthorizationCredentials

        driver = Driver(
            phone_e164="+15559876543",
            org_id=test_org.id,
            display_name="Test Driver 2",
        )
        db_session.add(driver)
        db_session.commit()
        db_session.refresh(driver)

        token = create_access_token({
            "sub": str(driver.driver_id),
            "scope": "driver",
            "phone": driver.phone_e164,
        })

        request = MagicMock()
        request.cookies.get.return_value = None
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        result = get_current_driver(request=request, creds=creds, db=db_session)
        assert result.driver_id == driver.driver_id
        assert result.phone_e164 == "+15559876543"
