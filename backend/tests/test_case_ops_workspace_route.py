"""Tests for case-ops incident workspace route."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import (
    Artifact,
    AuditEvent,
    Base,
    CaseNote,
    CaseTask,
    Event,
    Incident,
    Org,
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
def test_org(db_session):
    org = Org(name="CaseOps Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def test_user(db_session, test_org):
    user = User(
        email="caseops@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()
    return user


@pytest.fixture()
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id), "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}


def test_get_workspace_returns_incident_workspace_summary(
    client: TestClient,
    db_session,
    test_org,
    test_user,
    auth_headers,
):
    incident = Incident(
        org_id=test_org.id,
        status="evidence_capturing",
        case_status="awaiting_evidence",
        severity="serious",
        adc_vehicle_id="veh-42",
        adc_driver_id="drv-42",
        owner_user_id=test_user.id,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    db_session.add_all(
        [
            Artifact(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                artifact_type="dashcam",
                status="captured",
            ),
            Artifact(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                artifact_type="telemetry",
                status="pending",
            ),
            CaseTask(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                title="Follow up with witness",
                status="open",
                priority="high",
            ),
            CaseTask(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                title="Already done",
                status="completed",
                priority="low",
            ),
            CaseNote(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                body="Driver contacted.",
                created_by_user_id=test_user.id,
            ),
            CaseNote(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                body="Deleted note",
                is_deleted=True,
                created_by_user_id=test_user.id,
            ),
            Event(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                event_type="incident_started",
                actor_type="system",
                actor_id="system",
                occurred_at_utc=datetime.now(timezone.utc),
                payload={"step": "begin"},
            ),
            AuditEvent(
                org_id=test_org.id,
                incident_id=incident.incident_id,
                action="incident.case_status.patch",
                event_type="incident_case_status_updated",
                actor_type="user",
                actor_id=str(test_user.id),
                occurred_at_utc=datetime.now(timezone.utc),
                metadata_json={"to": "awaiting_evidence"},
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/incidents/{incident.incident_id}/workspace", headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["incident_id"] == str(incident.incident_id)
    assert payload["owner"]["user_id"] == str(test_user.id)
    assert payload["case_status"] == "awaiting_evidence"
    assert "readiness_state" in payload
    assert payload["completeness"]["percent"] >= 0
    assert isinstance(payload["blockers"], list)
    assert payload["evidence_summary"] == {
        "total": 2,
        "captured": 1,
        "pending": 1,
        "unavailable": 0,
    }
    assert len(payload["open_tasks"]) == 1
    assert payload["open_tasks"][0]["title"] == "Follow up with witness"
    assert len(payload["recent_notes"]) == 1
    assert payload["recent_notes"][0]["body"] == "Driver contacted."
    activity_types = {item["type"] for item in payload["activity"]}
    assert "incident_started" in activity_types
    assert "incident_case_status_updated" in activity_types


def test_get_workspace_enforces_org_tenancy(
    client: TestClient,
    db_session,
    auth_headers,
):
    other_org = Org(name="Other Org")
    db_session.add(other_org)
    db_session.commit()
    db_session.refresh(other_org)

    incident = Incident(
        org_id=other_org.id,
        status="open",
        case_status="new",
        severity="minor",
        adc_vehicle_id="veh-other",
        adc_driver_id="drv-other",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    response = client.get(
        f"/incidents/{incident.incident_id}/workspace", headers=auth_headers
    )
    assert response.status_code == 404


def test_get_workspace_allows_read_only_role(
    client: TestClient,
    db_session,
    test_org,
):
    user = User(
        email="readonly@example.com",
        password_hash=hash_password("testpass"),
        role="read_only",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()

    incident = Incident(
        org_id=test_org.id,
        status="open",
        case_status="new",
        severity="minor",
        adc_vehicle_id="veh-r",
        adc_driver_id="drv-r",
    )
    db_session.add(incident)
    db_session.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role})
    response = client.get(
        f"/incidents/{incident.incident_id}/workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
