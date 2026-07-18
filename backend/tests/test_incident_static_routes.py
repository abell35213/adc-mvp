"""Regression tests for case-ops incident static routes."""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import Base, Incident, Org, User, UserOrg
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(db_session):
    org = Org(name="Static Routes Org")
    other_org = Org(name="Other Org")
    user = User(email="static@example.com", password_hash=hash_password("secret"), role="safety_manager")
    db_session.add_all([org, other_org, user])
    db_session.commit()
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    own_incident = Incident(org_id=org.id, status="open", case_status="new", severity="serious")
    foreign_incident = Incident(org_id=other_org.id, status="open", case_status="new", severity="serious")
    db_session.add_all([own_incident, foreign_incident])
    db_session.commit()
    return user, own_incident, foreign_incident


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role})}"}


@pytest.mark.parametrize("path", ["/incidents/summary-metrics", "/incidents/alerts"])
def test_static_case_ops_routes_resolve_before_incident_uuid(client, seeded, path):
    user, _, _ = seeded
    response = client.get(path, headers=_headers(user))
    assert response.status_code == 200
    assert "uuid_parsing" not in response.text


@pytest.mark.parametrize("page_size", [50, 100])
def test_incident_queue_accepts_supported_page_sizes(client, seeded, page_size):
    user, _, _ = seeded
    response = client.get(
        f"/incidents/queue?sort=urgency&page=1&page_size={page_size}",
        headers=_headers(user),
    )
    assert response.status_code == 200
    assert response.json()["page_size"] == page_size


def test_incident_queue_rejects_page_size_over_backend_cap(client, seeded):
    user, _, _ = seeded
    response = client.get("/incidents/queue?page=1&page_size=101", headers=_headers(user))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "page_size"]


@pytest.mark.parametrize("path", ["/incidents/queue?page=1&page_size=50", "/incidents/summary-metrics", "/incidents/alerts"])
def test_static_case_ops_routes_still_require_authorization(client, path):
    response = client.get(path)
    assert response.status_code in {401, 403}


def test_valid_incident_uuid_detail_still_resolves_and_preserves_org_isolation(client, seeded):
    user, own_incident, foreign_incident = seeded
    own_response = client.get(f"/incidents/{own_incident.incident_id}", headers=_headers(user))
    assert own_response.status_code == 200
    assert own_response.json()["incident_id"] == str(own_incident.incident_id)

    foreign_response = client.get(f"/incidents/{foreign_incident.incident_id}", headers=_headers(user))
    assert foreign_response.status_code == 404


def test_static_route_names_are_not_treated_as_incident_uuid(client, seeded):
    user, _, _ = seeded
    response = client.get("/incidents/queue?sort=urgency&page=1&page_size=50", headers=_headers(user))
    assert response.status_code == 200
    assert "Input should be a valid UUID" not in response.text
