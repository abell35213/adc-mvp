"""Tests for the create_admin bootstrap script."""

import os
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make scripts importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.db.models import Base, User, Org, UserOrg


# A throwaway value that satisfies the script's minimum-length check; never used outside tests.
TEST_ADMIN_PASSWORD = "test-password-1234"


@pytest.fixture(autouse=True)
def _set_admin_password(monkeypatch):
    """Ensure ADMIN_PASSWORD is always set before invoking the script.

    The script intentionally refuses to run with an insecure default and requires
    an explicit password; tests must therefore provide one explicitly.
    """
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_ADMIN_PASSWORD)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


class TestCreateAdmin:
    def test_creates_admin_user(self, db_session):
        """create_admin.main() should create an admin user, org, and link."""
        from scripts import create_admin as ca

        with patch.object(ca, "SessionLocal", return_value=db_session):
            ca.main()

        user = db_session.query(User).filter(User.email == "admin@adc.local").first()
        assert user is not None
        assert user.role == "org_admin"

        org = db_session.query(Org).first()
        assert org is not None
        assert org.name == "ADC"

        link = (
            db_session.query(UserOrg)
            .filter(
                UserOrg.user_id == user.id,
                UserOrg.org_id == org.id,
            )
            .first()
        )
        assert link is not None

    def test_skips_if_already_exists(self, db_session, capsys):
        """Running twice should skip creation on the second run."""
        from scripts import create_admin as ca

        with patch.object(ca, "SessionLocal", return_value=db_session):
            ca.main()
            ca.main()

        captured = capsys.readouterr()
        assert "already exists" in captured.out

        users = db_session.query(User).all()
        assert len(users) == 1

    def test_refuses_when_password_missing(self, db_session, monkeypatch, capsys):
        """When ADMIN_PASSWORD is not set, the script must refuse non-interactive runs."""
        from scripts import create_admin as ca

        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        # Force non-interactive stdin so the script does not block on getpass().
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        with patch.object(ca, "SessionLocal", return_value=db_session):
            assert ca.main() == 2
        captured = capsys.readouterr()
        assert "ADMIN_PASSWORD" in captured.err

    def test_refuses_short_password(self, db_session, monkeypatch):
        """ADMIN_PASSWORD shorter than the minimum length should be rejected."""
        from scripts import create_admin as ca

        monkeypatch.setenv("ADMIN_PASSWORD", "short")
        with patch.object(ca, "SessionLocal", return_value=db_session):
            assert ca.main() == 2
