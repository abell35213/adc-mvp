"""Section 21 / Phase 7 route acceptance coverage."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import (
    Base,
    Driver,
    ExternalMapping,
    Org,
    OrgExportValidationRun,
    OrgPlanEntitlement,
    OrgTestIncidentRun,
    OrgVehicleRegistry,
    TrustSection,
    User,
    UserOrg,
)
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
def seeded_org(db_session):
    org = Org(name="Section 21 Acceptance Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    def _make_user(email: str, role: str) -> User:
        user = User(email=email, password_hash=hash_password("testpass"), role=role)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        db_session.add(UserOrg(user_id=user.id, org_id=org.id))
        db_session.commit()
        return user

    users = {
        "org_admin": _make_user("org-admin-section21@example.com", "org_admin"),
        "support_admin": _make_user(
            "support-admin-section21@example.com", "support_admin"
        ),
        "read_only": _make_user("readonly-section21@example.com", "read_only"),
    }

    db_session.add(
        OrgPlanEntitlement(
            org_id=org.id,
            plan_code="enterprise",
            entitlements_json={
                "demo.workspace": True,
                "demo.incident_seed": True,
                "trust.audit_controls": True,
            },
        )
    )

    for i in range(2):
        db_session.add(
            OrgVehicleRegistry(
                org_id=org.id,
                unit_number=f"veh-{i}",
                is_active=True,
                qr_deployment_status="distributed",
            )
        )
    for i in range(2):
        db_session.add(
            Driver(
                org_id=org.id,
                phone_e164=f"+1555111000{i}",
                display_name=f"Driver {i}",
                is_active=True,
            )
        )

    db_session.add(
        ExternalMapping(
            org_id=org.id,
            provider="samsara",
            domain="fleet",
            internal_entity_type="driver",
            internal_entity_id="driver-1",
            external_reference="ext-driver-1",
        )
    )
    db_session.add(OrgTestIncidentRun(org_id=org.id, status="completed"))
    db_session.add(OrgExportValidationRun(org_id=org.id, status="passed"))
    db_session.add(
        TrustSection(
            org_id=org.id,
            slug="security",
            title="Security",
            body_markdown="published security controls",
            sort_order=1,
            is_published=True,
            metadata_json={"audiences": ["manager"]},
        )
    )
    db_session.commit()
    return org, users


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_section21_endpoint_authn_and_authz(client, seeded_org):
    _, users = seeded_org

    for method, path in [
        ("get", "/org/entitlements"),
        ("get", "/demo/scenarios"),
        ("get", "/org/deployment-progress"),
        ("get", "/trust/sections"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401

    trust_internal_resp = client.put(
        "/trust/internal/sections",
        headers=_auth_headers(users["org_admin"]),
        json={
            "slug": "authz-denied",
            "title": "Denied",
            "body_markdown": "Should not be allowed",
            "sort_order": 2,
            "metadata": {},
        },
    )
    assert trust_internal_resp.status_code == 403

    deployment_patch_resp = client.patch(
        "/org/deployment-scope",
        headers=_auth_headers(users["read_only"]),
        json={"scope": "pilot"},
    )
    assert deployment_patch_resp.status_code == 403


def test_section21_entitlement_enforcement_hides_disabled_surfaces(
    client, seeded_org, db_session
):
    org, users = seeded_org
    row = (
        db_session.query(OrgPlanEntitlement)
        .filter(OrgPlanEntitlement.org_id == org.id)
        .one()
    )
    row.plan_code = "starter"
    row.entitlements_json = {
        "demo.workspace": False,
        "demo.incident_seed": False,
        "trust.audit_controls": False,
    }
    db_session.commit()

    demo_resp = client.get("/demo/scenarios", headers=_auth_headers(users["org_admin"]))
    assert demo_resp.status_code == 404

    trust_resp = client.get("/trust/sections", headers=_auth_headers(users["org_admin"]))
    assert trust_resp.status_code == 404


def test_section21_demo_reset_reseed_is_idempotent(client, seeded_org):
    _, users = seeded_org
    headers = _auth_headers(users["support_admin"])

    first_seed = client.post(
        "/demo/seed",
        headers=headers,
        json={"scenario_id": "driver_minor_collision"},
    )
    assert first_seed.status_code == 200

    first_reset = client.post("/demo/reset", headers=headers)
    assert first_reset.status_code == 200
    deleted_first = first_reset.json()["deleted"]
    assert all(count >= 0 for count in deleted_first.values())

    second_seed = client.post(
        "/demo/seed",
        headers=headers,
        json={"scenario_id": "driver_minor_collision"},
    )
    assert second_seed.status_code == 200

    second_reset = client.post("/demo/reset", headers=headers)
    assert second_reset.status_code == 200
    deleted_second = second_reset.json()["deleted"]
    assert set(deleted_second.keys()) == set(deleted_first.keys())


def test_section21_deployment_progress_and_readiness_states(client, seeded_org):
    _, users = seeded_org
    headers = _auth_headers(users["org_admin"])

    progress_resp = client.get("/org/deployment-progress", headers=headers)
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["scope"] == "pilot"
    assert progress["percent_complete"] >= 0
    assert isinstance(progress["coverage"], list)

    readiness_resp = client.get("/org/expansion-readiness", headers=headers)
    assert readiness_resp.status_code == 200
    readiness = readiness_resp.json()
    assert readiness["status"] in {
        "not_started",
        "planning",
        "pilot_ready",
        "scale_ready",
        "blocked",
    }
    assert isinstance(readiness["blockers"], list)


def test_section21_trust_publication_visibility_filters(client, seeded_org, db_session):
    org, users = seeded_org
    db_session.add(
        TrustSection(
            org_id=org.id,
            slug="draft-only",
            title="Draft Only",
            body_markdown="unpublished content",
            sort_order=99,
            is_published=False,
            metadata_json={"audiences": ["manager"]},
        )
    )
    db_session.commit()

    headers = _auth_headers(users["org_admin"])

    published_resp = client.get(
        "/trust/sections",
        headers=headers,
        params={"publication_state": "published", "audience": "manager"},
    )
    assert published_resp.status_code == 200
    published_slugs = [row["slug"] for row in published_resp.json()]
    assert "security" in published_slugs
    assert "draft-only" not in published_slugs

    all_resp = client.get(
        "/trust/sections",
        headers=headers,
        params={"publication_state": "all", "audience": "manager"},
    )
    assert all_resp.status_code == 200
    all_slugs = [row["slug"] for row in all_resp.json()]
    assert "draft-only" in all_slugs
