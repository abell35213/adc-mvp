
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import (
    Base,
    Driver,
    ExternalMapping,
    Org,
    OrgExportValidationRun,
    OrgTestIncidentRun,
    OrgVehicleRegistry,
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
def seeded_org(db_session):
    org = Org(name="Expansion Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    user = User(
        email="expansion@example.com",
        password_hash=hash_password("testpass"),
        role="org_admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(UserOrg(user_id=user.id, org_id=org.id))

    for i in range(3):
        db_session.add(
            OrgVehicleRegistry(
                org_id=org.id,
                unit_number=f"veh-{i}",
                is_active=True,
                qr_deployment_status="distributed" if i < 2 else "not_generated",
            )
        )

    for i in range(4):
        db_session.add(
            Driver(
                org_id=org.id,
                phone_e164=f"+15550000{i:03d}",
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
            internal_entity_id="drv-1",
            external_reference="ext-1",
        )
    )
    db_session.add(OrgTestIncidentRun(org_id=org.id, status="completed"))
    db_session.add(OrgExportValidationRun(org_id=org.id, status="passed"))
    db_session.commit()
    return org, user


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(seeded_org):
    _, user = seeded_org
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_deployment_scope_crud_and_progress_routes(client, auth_headers):
    get_scope = client.get("/org/deployment-scope", headers=auth_headers)
    assert get_scope.status_code == 200
    assert get_scope.json()["scope"] == "pilot"

    patch_scope = client.patch(
        "/org/deployment-scope",
        json={
            "scope": "partial_rollout",
            "targets": {
                "vehicles": 3,
                "drivers": 4,
                "admins": 1,
                "test_incidents": 1,
                "exports": 1,
            },
            "readiness_override": "planning",
            "source": "test",
        },
        headers=auth_headers,
    )
    assert patch_scope.status_code == 200
    assert patch_scope.json()["scope"] == "partial_rollout"
    assert patch_scope.json()["targets"]["vehicles"] == 3

    progress = client.get("/org/deployment-progress", headers=auth_headers)
    assert progress.status_code == 200
    payload = progress.json()
    assert payload["scope"] == "partial_rollout"
    assert payload["coverage"][0]["key"] == "vehicles"
    assert payload["blockers"] == [
        "qr_coverage_incomplete",
        "mapping_coverage_incomplete",
    ]

    readiness = client.get("/org/expansion-readiness", headers=auth_headers)
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "planning"
    assert readiness.json()["override_applied"] is True
