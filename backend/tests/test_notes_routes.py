"""Tests for incident notes routes."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import Base, CaseNote, Incident, Org, User, UserOrg
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
def org(db_session):
    org = Org(name="Notes Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def author_user(db_session, org):
    user = User(
        email="author@example.com",
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
def editor_user(db_session, org):
    user = User(
        email="editor@example.com",
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
def other_org_user(db_session):
    other_org = Org(name="Other Org")
    db_session.add(other_org)
    db_session.commit()
    db_session.refresh(other_org)

    user = User(
        email="other@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=other_org.id))
    db_session.commit()
    return user


@pytest.fixture()
def incident(db_session, org):
    incident = Incident(
        org_id=org.id,
        status="open",
        case_status="new",
        severity="minor",
        adc_vehicle_id="veh-notes",
        adc_driver_id="drv-notes",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_notes_crud_sets_edit_metadata_and_soft_delete_trail(
    client: TestClient,
    incident: Incident,
    author_user: User,
):
    create_response = client.post(
        f"/incidents/{incident.incident_id}/notes",
        json={"body": "Initial note", "note_type": "tagged", "tags": ["urgent"]},
        headers=_auth_headers(author_user),
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["note_type"] == "tagged"
    assert created["tags"] == ["urgent"]
    assert created["edited"] is False

    patch_response = client.patch(
        f"/incidents/{incident.incident_id}/notes",
        json={"note_id": created["note_id"], "body": "Updated note", "note_type": "decision"},
        headers=_auth_headers(author_user),
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["body"] == "Updated note"
    assert patched["note_type"] == "decision"
    assert patched["edited"] is True
    assert patched["edited_at_utc"] is not None
    assert patched["updated_at_utc"] is not None

    delete_response = client.request(
        method="DELETE",
        url=f"/incidents/{incident.incident_id}/notes",
        json={"note_id": created["note_id"]},
        headers=_auth_headers(author_user),
    )
    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["is_deleted"] is True
    assert deleted["deleted_at_utc"] is not None

    list_default_response = client.get(
        f"/incidents/{incident.incident_id}/notes", headers=_auth_headers(author_user)
    )
    assert list_default_response.status_code == 200
    assert list_default_response.json()["items"] == []

    list_with_deleted_response = client.get(
        f"/incidents/{incident.incident_id}/notes?include_deleted=true",
        headers=_auth_headers(author_user),
    )
    assert list_with_deleted_response.status_code == 200
    items = list_with_deleted_response.json()["items"]
    assert len(items) == 1
    assert items[0]["is_deleted"] is True


def test_non_author_cannot_edit_or_delete_note(
    client: TestClient,
    db_session,
    incident: Incident,
    author_user: User,
    editor_user: User,
):
    note = CaseNote(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        body="Author note",
        created_by_user_id=author_user.id,
    )
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    patch_response = client.patch(
        f"/incidents/{incident.incident_id}/notes",
        json={"note_id": str(note.note_id), "body": "Trying to edit"},
        headers=_auth_headers(editor_user),
    )
    assert patch_response.status_code == 403

    delete_response = client.request(
        method="DELETE",
        url=f"/incidents/{incident.incident_id}/notes",
        json={"note_id": str(note.note_id)},
        headers=_auth_headers(editor_user),
    )
    assert delete_response.status_code == 403


def test_notes_routes_enforce_org_isolation(
    client: TestClient,
    incident: Incident,
    other_org_user: User,
):
    list_response = client.get(
        f"/incidents/{incident.incident_id}/notes", headers=_auth_headers(other_org_user)
    )
    assert list_response.status_code == 404

    create_response = client.post(
        f"/incidents/{incident.incident_id}/notes",
        json={"body": "No access"},
        headers=_auth_headers(other_org_user),
    )
    assert create_response.status_code == 404
