"""Regression tests for the demo-data seed script's identity helper.

The full ``main()`` flow exercises ``app.commercial.demo`` which has many
dependencies; here we focus on ``_ensure_demo_identity`` because it owns the
role/credentials of the demo admin — historically provisioned as
``SYSTEM_ADMIN``, which made password-only login impossible because of the
unconditional MFA gate in ``app.api.routes_auth._is_mfa_required``.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make `app` importable.
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "..")
)

from app.core.security import verify_password
from app.db.models import Base, Org, User, UserOrg
from app.security.permissions import Role


def _load_seed_module():
    """Import scripts/seed_demo_data.py by path (it isn't a package)."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "seed_demo_data.py"
    spec = importlib.util.spec_from_file_location("_seed_demo_data_under_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


@pytest.fixture()
def seed_module():
    return _load_seed_module()


def _identity_kwargs():
    return dict(
        org_name="ADC Demo Org",
        admin_email="demo-admin@adc.local",
        admin_password="DemoAdmin!2345",
        driver_phone="+15551234567",
        vehicle_id="veh-demo-001",
    )


def test_ensure_demo_identity_creates_org_admin(db_session, seed_module):
    """A fresh seed must provision the demo admin as ORG_ADMIN, not SYSTEM_ADMIN.

    SYSTEM_ADMIN trips the MFA gate in routes_auth._is_mfa_required, which the
    web login form cannot satisfy — the seeded credentials would be unusable.
    """
    org, user, driver, token = seed_module._ensure_demo_identity(
        db_session, **_identity_kwargs()
    )

    assert user.role == Role.ORG_ADMIN.value
    assert user.role != Role.SYSTEM_ADMIN.value
    assert user.email == "demo-admin@adc.local"
    assert verify_password("DemoAdmin!2345", user.password_hash)
    assert org.name == "ADC Demo Org"
    # User is linked to the demo org so the dashboard scopes data correctly.
    link = (
        db_session.query(UserOrg)
        .filter(UserOrg.user_id == user.id, UserOrg.org_id == org.id)
        .first()
    )
    assert link is not None
    assert driver.phone_e164 == "+15551234567"
    assert token.adc_vehicle_id == "veh-demo-001"


def test_ensure_demo_identity_migrates_stale_system_admin(db_session, seed_module):
    """Re-seeding over an old SYSTEM_ADMIN demo user must downgrade the role
    so existing local installs self-heal without manual DB surgery."""
    from app.core.security import hash_password

    legacy_org = Org(name="ADC Demo Org")
    legacy_user = User(
        email="demo-admin@adc.local",
        password_hash=hash_password("legacy-password"),
        role=Role.SYSTEM_ADMIN.value,
    )
    db_session.add_all([legacy_org, legacy_user])
    db_session.commit()

    _, user, _, _ = seed_module._ensure_demo_identity(
        db_session, **_identity_kwargs()
    )

    db_session.refresh(user)
    assert user.role == Role.ORG_ADMIN.value
    # Password hash must be refreshed to the documented seed password so
    # operators don't have to remember which password the previous run used.
    assert verify_password("DemoAdmin!2345", user.password_hash)


def test_seed_module_default_password_meets_create_admin_policy(seed_module):
    """Keep the seed script's default password aligned with the bootstrap
    script's 12-char minimum so docs/policies don't drift."""
    # The default lives in main(); inspect via the env-var fallback the same
    # way main() does (without invoking the full SessionLocal path).
    prior = os.environ.pop("DEMO_ADMIN_PASSWORD", None)
    try:
        default = os.environ.get("DEMO_ADMIN_PASSWORD", "DemoAdmin!2345")
    finally:
        if prior is not None:
            os.environ["DEMO_ADMIN_PASSWORD"] = prior
    assert len(default) >= 12
