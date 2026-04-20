"""Tests for trust center service and API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, Org, OrgPlanEntitlement, TrustSection, User, UserOrg
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
    test_session = sessionmaker(bind=engine)
    session = test_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_org(db_session):
    org = Org(name="Trust Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def org_admin_user(db_session, test_org):
    user = User(
        email="org-admin-trust@example.com",
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
def support_admin_user(db_session, test_org):
    user = User(
        email="support-admin-trust@example.com",
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
def trust_seed(db_session, test_org):
    db_session.add(
        OrgPlanEntitlement(
            org_id=test_org.id,
            plan_code="enterprise",
            entitlements_json={"trust.audit_controls": True},
        )
    )
    db_session.add_all(
        [
            TrustSection(
                org_id=test_org.id,
                slug="security",
                title="Security",
                body_markdown="published-manager",
                sort_order=2,
                is_published=True,
                metadata_json={"audiences": ["manager"]},
            ),
            TrustSection(
                org_id=test_org.id,
                slug="privacy",
                title="Privacy",
                body_markdown="published-all",
                sort_order=1,
                is_published=True,
                metadata_json={"audiences": ["manager", "driver"]},
            ),
            TrustSection(
                org_id=test_org.id,
                slug="draft-internal",
                title="Draft",
                body_markdown="draft",
                sort_order=3,
                is_published=False,
                metadata_json={"audiences": ["support"]},
            ),
        ]
    )
    db_session.commit()


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


def test_get_trust_sections_and_summary(client, org_admin_user, trust_seed):
    sections_resp = client.get(
        "/trust/sections",
        headers=_auth_headers(org_admin_user),
        params={"audience": "manager"},
    )
    assert sections_resp.status_code == 200
    sections = sections_resp.json()
    assert [section["slug"] for section in sections] == ["privacy", "security"]

    summary_resp = client.get(
        "/trust/summary",
        headers=_auth_headers(org_admin_user),
        params={"audience": "manager"},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["section_count"] == 2
    assert summary["section_slugs"] == ["privacy", "security"]


def test_internal_update_publish_unpublish_emits_audit_events(
    client,
    db_session,
    support_admin_user,
    trust_seed,
):
    create_resp = client.put(
        "/trust/internal/sections",
        headers=_auth_headers(support_admin_user),
        json={
            "slug": "compliance",
            "title": "Compliance",
            "body_markdown": "compliance controls",
            "sort_order": 0,
            "metadata": {"audiences": ["manager"]},
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    section_id = created["section_id"]

    publish_resp = client.post(
        f"/trust/internal/sections/{section_id}/publish",
        headers=_auth_headers(support_admin_user),
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["is_published"] is True

    unpublish_resp = client.post(
        f"/trust/internal/sections/{section_id}/unpublish",
        headers=_auth_headers(support_admin_user),
    )
    assert unpublish_resp.status_code == 200
    assert unpublish_resp.json()["is_published"] is False

    events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "trust_center_updated")
        .order_by(AuditEvent.occurred_at_utc.asc())
        .all()
    )
    assert len(events) == 3


def test_internal_endpoints_restricted(client, org_admin_user, trust_seed):
    response = client.put(
        "/trust/internal/sections",
        headers=_auth_headers(org_admin_user),
        json={
            "slug": "attempt",
            "title": "Nope",
            "body_markdown": "denied",
            "sort_order": 5,
            "metadata": {},
        },
    )
    assert response.status_code == 403
