"""Tests for demo orchestration API routes."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, Org, User, UserOrg
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
    org = Org(name="Demo Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def support_admin_user(db_session, test_org):
    user = User(
        email="support-admin@example.com",
        password_hash=hash_password("testpass"),
        role="support_admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()
    return user


@pytest.fixture()
def org_admin_user(db_session, test_org):
    user = User(
        email="org-admin@example.com",
        password_hash=hash_password("testpass"),
        role="org_admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()
    return user


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


def _auth_headers(user):
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_demo_scenarios_list_and_launch_flow(client, support_admin_user, db_session):
    list_resp = client.get("/demo/scenarios", headers=_auth_headers(support_admin_user))
    assert list_resp.status_code == 200
    assert any(row["scenario_id"] == "driver_minor_collision" for row in list_resp.json())

    launch_resp = client.post(
        "/demo/scenarios/driver_minor_collision/launch",
        headers=_auth_headers(support_admin_user),
    )
    assert launch_resp.status_code == 200
    launch_payload = launch_resp.json()
    assert launch_payload["scenario_id"] == "driver_minor_collision"
    assert launch_payload["incident_id"]
    assert launch_payload["export_id"]

    audit_types = {
        row.event_type for row in db_session.query(AuditEvent).all()
    }
    assert "demo_scenario_launched" in audit_types
    assert "demo_tenant_reset" in audit_types


def test_demo_mutation_routes_require_internal_roles(client, org_admin_user):
    reset_resp = client.post("/demo/reset", headers=_auth_headers(org_admin_user))
    assert reset_resp.status_code == 403

    seed_resp = client.post("/demo/seed", headers=_auth_headers(org_admin_user), json={})
    assert seed_resp.status_code == 403
