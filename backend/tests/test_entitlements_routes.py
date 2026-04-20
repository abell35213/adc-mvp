"""Tests for org plan + entitlement routes."""

import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, Org, User, UserOrg
from app.db.repo.org_content import upsert_org_plan_entitlement
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
    org = Org(name="Commercial Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


def _create_user(db_session, org, *, role: str, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("testpass"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    db_session.commit()
    return user


@pytest.fixture()
def org_admin_user(db_session, test_org):
    return _create_user(
        db_session, test_org, role="org_admin", email="org-admin@example.com"
    )


@pytest.fixture()
def support_admin_user(db_session, test_org):
    return _create_user(
        db_session, test_org, role="support_admin", email="support-admin@example.com"
    )


@pytest.fixture()
def support_agent_user(db_session, test_org):
    return _create_user(
        db_session, test_org, role="support_agent", email="support-agent@example.com"
    )


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


def test_org_plan_entitlements_and_modules_are_ui_safe(client, org_admin_user):
    plan_resp = client.get("/org/plan", headers=_auth_headers(org_admin_user))
    assert plan_resp.status_code == 200
    assert plan_resp.json()["plan_code"] == "starter"

    ent_resp = client.get("/org/entitlements", headers=_auth_headers(org_admin_user))
    assert ent_resp.status_code == 200
    payload = ent_resp.json()
    assert set(payload.keys()) == {
        "org_id",
        "plan_code",
        "billing_status",
        "modules",
        "entitlements",
        "feature_flags",
        "internal_override_eligible_roles",
    }
    assert isinstance(payload["modules"], list)
    assert isinstance(payload["entitlements"], list)
    assert isinstance(payload["feature_flags"], dict)

    modules_resp = client.get("/org/modules", headers=_auth_headers(org_admin_user))
    assert modules_resp.status_code == 200
    modules_payload = modules_resp.json()
    assert set(modules_payload.keys()) == {"org_id", "plan_code", "modules"}


def test_patch_entitlements_emits_plan_and_feature_audit_events(
    client, db_session, org_admin_user, test_org
):
    upsert_org_plan_entitlement(db_session, test_org.id, plan_code="starter")

    resp = client.patch(
        "/org/entitlements",
        headers=_auth_headers(org_admin_user),
        json={
            "plan_code": "growth",
            "entitlements": {"reporting.dashboard": True},
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["plan_code"] == "growth"
    assert payload["feature_flags"]["reporting.dashboard"] is True

    events = db_session.query(AuditEvent).all()
    event_types = {row.event_type for row in events}
    assert "org_plan_changed" in event_types
    assert "feature_entitlement_updated" in event_types


def test_patch_entitlements_internal_override_requires_internal_role(
    client, org_admin_user
):
    resp = client.patch(
        "/org/entitlements",
        headers=_auth_headers(org_admin_user),
        json={
            "entitlements": {"demo.workspace": True},
            "internal_override": {
                "reason": "demo assistance",
                "ticket_id": "SUP-123",
                "actor_path": "support",
            },
        },
    )
    assert resp.status_code == 403


def test_patch_entitlements_internal_override_writes_audit_metadata(
    client, db_session, support_admin_user
):
    resp = client.patch(
        "/org/entitlements",
        headers=_auth_headers(support_admin_user),
        json={
            "entitlements": {"demo.workspace": True},
            "internal_override": {
                "reason": "demo support enablement",
                "ticket_id": str(uuid.uuid4()),
                "actor_path": "demo_support",
            },
        },
    )
    assert resp.status_code == 200

    feature_event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "feature_entitlement_updated")
        .order_by(AuditEvent.occurred_at_utc.desc())
        .first()
    )
    assert feature_event is not None
    metadata = feature_event.metadata_json or {}
    assert metadata["internal_override"]["applied"] is True
    assert metadata["internal_override"]["actor_role"] == "support_admin"


def test_patch_entitlements_allows_support_agent_capability(client, support_agent_user):
    resp = client.patch(
        "/org/entitlements",
        headers=_auth_headers(support_agent_user),
        json={"entitlements": {"reporting.dashboard": True}},
    )
    assert resp.status_code == 200
