"""Authorization regression coverage for protected routes."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, Driver, Export, Incident, Org, User, UserOrg
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


def test_admin_vehicle_list_allows_read_only_and_admin_roles(client, db_session):
    org = Org(name="Admin Org")
    manager = User(email="manager@ex.com", password_hash=hash_password("x"), role="read_only")
    admin = User(email="admin@ex.com", password_hash=hash_password("x"), role="admin")
    db_session.add_all([org, manager, admin])
    db_session.commit()
    db_session.add_all([UserOrg(user_id=manager.id, org_id=org.id), UserOrg(user_id=admin.id, org_id=org.id)])
    db_session.commit()

    readonly = client.get("/admin/vehicles", headers=_user_headers(manager.id, manager.role))
    allowed = client.get("/admin/vehicles", headers=_user_headers(admin.id, admin.role))

    assert readonly.status_code == 200
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
