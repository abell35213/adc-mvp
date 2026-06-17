"""Authorization regression coverage for protected routes."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, CaseNote, CaseTask, Driver, Export, Incident, Org, User, UserOrg
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
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _user_headers(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token({"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def _driver_headers(driver_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token({"sub": str(driver_id), "scope": "driver"})
    return {"Authorization": f"Bearer {token}"}


def _create_org_user(db_session, *, org_name: str, email: str, role: str = "safety_manager"):
    org = Org(name=org_name)
    user = User(email=email, password_hash=hash_password("x"), role=role)
    db_session.add_all([org, user])
    db_session.commit()
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    db_session.commit()
    return org, user


def test_incident_create_requires_org_membership(client, db_session):
    user = User(email="no-org@ex.com", password_hash=hash_password("x"), role="safety_manager")
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/incidents/",
        json={"severity": "minor", "adc_vehicle_id": "v1", "samsara_vehicle_id": "s1", "adc_driver_id": "d1"},
        headers=_user_headers(user.id, user.role),
    )
    assert response.status_code == 403


def test_export_download_checks_org_membership(client, db_session):
    member_org = Org(name="Member")
    foreign_org = Org(name="Foreign")
    user = User(email="member@ex.com", password_hash=hash_password("x"), role="safety_manager")
    db_session.add_all([member_org, foreign_org, user])
    db_session.commit()
    db_session.add(UserOrg(user_id=user.id, org_id=member_org.id))
    incident = Incident(status="open", org_id=foreign_org.id)
    db_session.add(incident)
    db_session.commit()
    export = Export(incident_id=incident.incident_id, org_id=foreign_org.id, status="ready", s3_bucket="b", s3_key="k")
    db_session.add(export)
    db_session.commit()

    response = client.get(f"/exports/{export.export_id}/download", headers=_user_headers(user.id, user.role))
    assert response.status_code == 403
    audit = db_session.query(AuditEvent).filter(AuditEvent.event_type == "authorization_failed").first()
    assert audit is not None
    assert audit.outcome == "failure"


def test_admin_vehicle_list_requires_admin_capability(client, db_session):
    org = Org(name="Admin Org")
    manager = User(email="manager@ex.com", password_hash=hash_password("x"), role="read_only")
    admin = User(email="admin@ex.com", password_hash=hash_password("x"), role="admin")
    db_session.add_all([org, manager, admin])
    db_session.commit()
    db_session.add_all([UserOrg(user_id=manager.id, org_id=org.id), UserOrg(user_id=admin.id, org_id=org.id)])
    db_session.commit()

    readonly = client.get("/admin/vehicles", headers=_user_headers(manager.id, manager.role))
    allowed = client.get("/admin/vehicles", headers=_user_headers(admin.id, admin.role))

    assert readonly.status_code == 403
    assert allowed.status_code == 200


def test_driver_status_requires_incident_ownership(client, db_session):
    org = Org(name="Driver Org")
    db_session.add(org)
    db_session.commit()
    owner = Driver(org_id=org.id, phone_e164="+15551000001", display_name="owner")
    other = Driver(org_id=org.id, phone_e164="+15551000002", display_name="other")
    db_session.add_all([owner, other])
    db_session.commit()
    incident = Incident(status="open", org_id=org.id, adc_driver_id=str(owner.driver_id))
    db_session.add(incident)
    db_session.commit()

    denied = client.get(
        f"/driver/incidents/{incident.incident_id}/status",
        headers=_driver_headers(other.driver_id),
    )
    assert denied.status_code == 404


def test_phase6_org_settings_write_denied_for_read_only(client, db_session):
    org = Org(name="Read Only Org")
    user = User(email="readonly@ex.com", password_hash=hash_password("x"), role="read_only")
    db_session.add_all([org, user])
    db_session.commit()
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    db_session.commit()

    denied = client.patch(
        "/org/settings",
        json={"display_name": "Updated"},
        headers=_user_headers(user.id, user.role),
    )

    assert denied.status_code == 403


def test_phase6_import_write_denied_for_read_only(client, db_session):
    org = Org(name="Import Org")
    user = User(email="readonly-import@ex.com", password_hash=hash_password("x"), role="read_only")
    db_session.add_all([org, user])
    db_session.commit()
    db_session.add(UserOrg(user_id=user.id, org_id=org.id))
    db_session.commit()

    denied = client.post(
        "/org/vehicles/import",
        json={
            "provider": "csv_upload",
            "csv_content": "unit_number,vin\\nUNIT-1,123",
            "header_mapping": {"unit_number": "unit_number", "vin": "vin"},
            "inactive_unit_numbers": [],
        },
        headers=_user_headers(user.id, user.role),
    )
    allowed_readiness = client.get(
        "/org/onboarding/status",
        headers=_user_headers(user.id, user.role),
    )

    assert denied.status_code == 403
    assert allowed_readiness.status_code == 200


def test_incident_and_export_lists_are_org_scoped(client, db_session):
    org_a, user_a = _create_org_user(db_session, org_name="Org A", email="org-a@ex.com")
    org_b = Org(name="Org B")
    db_session.add(org_b)
    db_session.commit()
    incident_a = Incident(status="open", org_id=org_a.id, adc_vehicle_id="a-vehicle")
    incident_b = Incident(status="open", org_id=org_b.id, adc_vehicle_id="b-vehicle")
    db_session.add_all([incident_a, incident_b])
    db_session.commit()
    export_a = Export(incident_id=incident_a.incident_id, org_id=org_a.id, status="ready")
    export_b = Export(incident_id=incident_b.incident_id, org_id=org_b.id, status="ready")
    db_session.add_all([export_a, export_b])
    db_session.commit()

    incident_response = client.get("/incidents/", headers=_user_headers(user_a.id, user_a.role))
    export_response = client.get("/exports/", headers=_user_headers(user_a.id, user_a.role))

    assert incident_response.status_code == 200
    assert [item["incident_id"] for item in incident_response.json()] == [str(incident_a.incident_id)]
    assert export_response.status_code == 200
    assert [item["export_id"] for item in export_response.json()] == [str(export_a.export_id)]


def test_export_status_and_contents_do_not_cross_orgs(client, db_session):
    org_a, user_a = _create_org_user(db_session, org_name="Org A", email="status-a@ex.com")
    org_b = Org(name="Org B")
    db_session.add(org_b)
    db_session.commit()
    incident_b = Incident(status="open", org_id=org_b.id)
    db_session.add(incident_b)
    db_session.commit()
    export_b = Export(incident_id=incident_b.incident_id, org_id=org_b.id, status="ready")
    db_session.add(export_b)
    db_session.commit()

    headers = _user_headers(user_a.id, user_a.role)
    assert client.get(f"/exports/{export_b.export_id}", headers=headers).status_code == 403
    assert client.get(f"/exports/{export_b.export_id}/status", headers=headers).status_code == 403
    assert client.get(f"/exports/{export_b.export_id}/contents", headers=headers).status_code == 403


def test_notes_and_tasks_do_not_cross_orgs(client, db_session):
    org_a, user_a = _create_org_user(db_session, org_name="Org A", email="case-a@ex.com")
    org_b = Org(name="Org B")
    db_session.add(org_b)
    db_session.commit()
    incident_b = Incident(status="open", org_id=org_b.id)
    db_session.add(incident_b)
    db_session.commit()
    note_b = CaseNote(org_id=org_b.id, incident_id=incident_b.incident_id, body="foreign")
    task_b = CaseTask(org_id=org_b.id, incident_id=incident_b.incident_id, title="foreign")
    db_session.add_all([note_b, task_b])
    db_session.commit()

    headers = _user_headers(user_a.id, user_a.role)
    notes_response = client.get(f"/incidents/{incident_b.incident_id}/notes", headers=headers)
    tasks_response = client.get(f"/incidents/{incident_b.incident_id}/tasks", headers=headers)
    patch_task_response = client.patch(
        f"/tasks/{task_b.task_id}",
        json={"title": "should not update"},
        headers=headers,
    )

    assert notes_response.status_code == 404
    assert tasks_response.status_code == 404
    assert patch_task_response.status_code == 404
    db_session.refresh(task_b)
    assert task_b.title == "foreign"


def test_legacy_null_org_task_can_be_mutated_through_incident_org(client, db_session):
    org_a, user_a = _create_org_user(db_session, org_name="Legacy Org", email="legacy-task@ex.com")
    incident_a = Incident(status="open", org_id=org_a.id)
    db_session.add(incident_a)
    db_session.commit()
    task = CaseTask(org_id=None, incident_id=incident_a.incident_id, title="legacy")
    db_session.add(task)
    db_session.commit()

    response = client.patch(
        f"/tasks/{task.task_id}",
        json={"title": "updated legacy"},
        headers=_user_headers(user_a.id, user_a.role),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "updated legacy"
    db_session.refresh(task)
    assert task.title == "updated legacy"
