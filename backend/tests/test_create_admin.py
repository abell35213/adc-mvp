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
        assert user.role == "admin"

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
