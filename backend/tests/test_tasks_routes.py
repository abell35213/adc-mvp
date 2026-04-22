"""Tests for incident task management routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, CaseTask, Event, Incident, Org, User, UserOrg
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
    org = Org(name="Tasks Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def user(db_session, org):
    user = User(
        email="tasks@example.com",
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
def assignee(db_session, org):
    user = User(
        email="assignee@example.com",
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
def incident(db_session, org):
    incident = Incident(
        org_id=org.id,
        status="open",
        case_status="new",
        severity="minor",
        adc_vehicle_id="veh-task",
        adc_driver_id="drv-task",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_task_routes_create_list_patch_complete_cancel_with_audit(
    client: TestClient,
    db_session,
    incident: Incident,
    user: User,
    assignee: User,
):
    due_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    create_response = client.post(
        f"/incidents/{incident.incident_id}/tasks",
        json={
            "title": "Collect witness statement",
            "description": "Reach out before EOD",
            "task_type": "follow_up",
            "priority": "high",
            "due_at_utc": due_at,
        },
        headers=_auth_headers(user),
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "open"
    assert created["task_type"] == "follow_up"
    assert created["overdue"] is True

    list_response = client.get(
        f"/incidents/{incident.incident_id}/tasks",
        headers=_auth_headers(user),
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    patch_response = client.patch(
        f"/tasks/{created['task_id']}",
        json={"assigned_to_user_id": str(assignee.id), "priority": "urgent"},
        headers=_auth_headers(user),
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["assigned_to_user_id"] == str(assignee.id)
    assert patched["assigned_at_utc"] is not None
    assert patched["priority"] == "urgent"

    complete_response = client.post(
        f"/tasks/{created['task_id']}/complete",
        headers=_auth_headers(user),
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["status"] == "completed"
    assert completed["completed_at_utc"] is not None
    assert completed["overdue"] is False

    invalid_transition = client.post(
        f"/tasks/{created['task_id']}/cancel",
        json={"reason": "No longer needed"},
        headers=_auth_headers(user),
    )
    assert invalid_transition.status_code == 409

    second_task = CaseTask(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        title="Second",
        status="open",
        priority="medium",
    )
    db_session.add(second_task)
    db_session.commit()
    db_session.refresh(second_task)

    cancel_response = client.post(
        f"/tasks/{second_task.task_id}/cancel",
        json={"reason": "Duplicate"},
        headers=_auth_headers(user),
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["canceled_reason"] == "Duplicate"

    events = db_session.query(AuditEvent).filter(AuditEvent.incident_id == incident.incident_id).all()
    event_types = {event.event_type for event in events}
    assert {
        "incident_task_created",
        "incident_task_reassigned",
        "incident_task_completed",
        "incident_task_cancelled",
    }.issubset(event_types)

    system_events = db_session.query(Event).filter(Event.incident_id == incident.incident_id).all()
    system_event_types = {event.event_type for event in system_events}
    assert {
        "incident_task_created",
        "incident_task_reassigned",
        "incident_task_completed",
        "incident_task_cancelled",
    }.issubset(system_event_types)


def test_task_patch_rejects_invalid_status_transition(
    client: TestClient,
    db_session,
    incident: Incident,
    user: User,
):
    task = CaseTask(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        title="Immutable done task",
        status="completed",
        priority="low",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.patch(
        f"/tasks/{task.task_id}",
        json={"status": "open"},
        headers=_auth_headers(user),
    )
    assert response.status_code == 409


def test_claims_user_task_write_allowed_and_read_only_denied(
    client: TestClient,
    db_session,
    incident: Incident,
):
    claims_user = User(
        email="claims-tasks@example.com",
        password_hash=hash_password("testpass"),
        role="claims_user",
    )
    read_only_user = User(
        email="readonly-tasks@example.com",
        password_hash=hash_password("testpass"),
        role="read_only",
    )
    db_session.add_all([claims_user, read_only_user])
    db_session.commit()
    db_session.refresh(claims_user)
    db_session.refresh(read_only_user)
    db_session.add_all(
        [
            UserOrg(user_id=claims_user.id, org_id=incident.org_id),
            UserOrg(user_id=read_only_user.id, org_id=incident.org_id),
        ]
    )
    db_session.commit()

    create_response = client.post(
        f"/incidents/{incident.incident_id}/tasks",
        json={"title": "Claims task"},
        headers=_auth_headers(claims_user),
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]

    list_response = client.get(
        f"/incidents/{incident.incident_id}/tasks",
        headers=_auth_headers(read_only_user),
    )
    assert list_response.status_code == 200

    patch_response = client.patch(
        f"/tasks/{task_id}",
        json={"priority": "high"},
        headers=_auth_headers(read_only_user),
    )
    assert patch_response.status_code == 403

    complete_response = client.post(
        f"/tasks/{task_id}/complete",
        headers=_auth_headers(read_only_user),
    )
    assert complete_response.status_code == 403
