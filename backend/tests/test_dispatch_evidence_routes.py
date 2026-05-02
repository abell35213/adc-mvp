"""API tests for the dispatch / weigh / loading dock manual-entry routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import Base, Org, User, UserOrg
from app.db.session import get_db
from app.main import app


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
def org(db_session):
    org = Org(name="Dispatch Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def member_user(db_session, org):
    user = User(
        email="member@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    db_session.commit()
    return user


@pytest.fixture()
def read_only_user(db_session, org):
    user = User(
        email="readonly@example.com",
        password_hash=hash_password("testpass"),
        role="read_only",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    db_session.commit()
    return user


@pytest.fixture()
def other_org_user(db_session):
    other = Org(name="Other Org")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    user = User(
        email="other@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=other.id))
    db_session.commit()
    return user


def _auth(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


class TestDispatchInstructionRoutes:
    def test_create_list_patch_round_trip(self, client, org, member_user):
        create_resp = client.post(
            f"/orgs/{org.id}/dispatch-instructions",
            json={
                "dispatch_id": "DSP-1",
                "load_number": "LD-1",
                "forced_dispatch_flag": True,
            },
            headers=_auth(member_user),
        )
        assert create_resp.status_code == 200, create_resp.text
        record = create_resp.json()
        assert record["dispatch_id"] == "DSP-1"
        assert record["forced_dispatch_flag"] is True
        assert record["source"] == "manual"

        list_resp = client.get(
            f"/orgs/{org.id}/dispatch-instructions",
            headers=_auth(member_user),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()["items"]) == 1

        patch_resp = client.patch(
            f"/orgs/{org.id}/dispatch-instructions/{record['id']}",
            json={"load_number": "LD-2"},
            headers=_auth(member_user),
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["load_number"] == "LD-2"

    def test_other_org_cannot_access(self, client, org, other_org_user):
        resp = client.get(
            f"/orgs/{org.id}/dispatch-instructions",
            headers=_auth(other_org_user),
        )
        assert resp.status_code == 404

    def test_read_only_user_cannot_create(
        self, client, org, read_only_user
    ):
        resp = client.post(
            f"/orgs/{org.id}/dispatch-instructions",
            json={"dispatch_id": "DSP-2"},
            headers=_auth(read_only_user),
        )
        assert resp.status_code == 403


class TestWeighStationRoutes:
    def test_create_with_over_limit_inferred(self, client, org, member_user):
        resp = client.post(
            f"/orgs/{org.id}/weigh-station-reports",
            json={
                "ticket_number": "WS-1",
                "gross_weight_lb": 82000,
                "legal_limit_lb": 80000,
            },
            headers=_auth(member_user),
        )
        assert resp.status_code == 200, resp.text
        record = resp.json()
        assert record["is_over_legal_limit"] is True
        assert record["source"] == "manual"


class TestLoadingDockRoutes:
    def test_create_and_attach_photo(
        self, client, db_session, org, member_user
    ):
        from app.db.models import Artifact, Incident

        incident = Incident(org_id=org.id, status="open")
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        # Create the dock report.
        create_resp = client.post(
            f"/orgs/{org.id}/loading-dock-reports",
            json={
                "facility_name": "Acme Dock",
                "is_improperly_loaded": True,
            },
            headers=_auth(member_user),
        )
        assert create_resp.status_code == 200, create_resp.text
        report_id = create_resp.json()["id"]

        # Pre-create an Artifact row (the upload pipeline creates these in
        # production; the manual-entry flow just links them).
        artifact = Artifact(
            org_id=org.id,
            incident_id=incident.incident_id,
            artifact_type="loading_dock_photo",
            status="captured",
        )
        db_session.add(artifact)
        db_session.commit()
        db_session.refresh(artifact)

        attach_resp = client.post(
            f"/orgs/{org.id}/loading-dock-reports/{report_id}/photos",
            json={"artifact_id": str(artifact.artifact_id)},
            headers=_auth(member_user),
        )
        assert attach_resp.status_code == 200, attach_resp.text

        db_session.refresh(artifact)
        assert str(artifact.loading_dock_report_id) == report_id
