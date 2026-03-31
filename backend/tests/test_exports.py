"""Focused test coverage for the exports list endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

try:
    from app.main import app
    from app.db.models import Base, Export, Incident, Org, User, UserOrg
    from app.db.session import get_db
    from app.core.security import create_access_token, hash_password
except ModuleNotFoundError:
    pytest.skip("FastAPI app not available for testing", allow_module_level=True)


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
def test_org(db_session):
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def other_org(db_session):
    org = Org(name="Other Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def test_user(db_session, test_org):
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    link = UserOrg(user_id=user.id, org_id=test_org.id)
    db_session.add(link)
    db_session.commit()
    return user


@pytest.fixture()
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id), "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_list_exports_empty(client: TestClient, auth_headers) -> None:
    response = client.get("/exports/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_exports_filters_by_org_including_legacy_null_org_exports(
    client: TestClient,
    db_session,
    test_org,
    other_org,
    auth_headers,
) -> None:
    now = datetime.now(timezone.utc)

    caller_incident = Incident(org_id=test_org.id, status="open")
    other_incident = Incident(org_id=other_org.id, status="open")
    db_session.add_all([caller_incident, other_incident])
    db_session.commit()
    db_session.refresh(caller_incident)
    db_session.refresh(other_incident)

    caller_export = Export(
        incident_id=caller_incident.incident_id,
        org_id=test_org.id,
        status="ready",
        created_at_utc=now - timedelta(minutes=2),
    )
    legacy_caller_export = Export(
        incident_id=caller_incident.incident_id,
        org_id=None,
        status="processing",
        created_at_utc=now - timedelta(minutes=1),
    )
    other_org_export = Export(
        incident_id=other_incident.incident_id,
        org_id=other_org.id,
        status="failed",
        created_at_utc=now,
    )

    db_session.add_all([caller_export, legacy_caller_export, other_org_export])
    db_session.commit()

    response = client.get("/exports/", headers=auth_headers)
    assert response.status_code == 200

    rows = response.json()
    assert len(rows) == 2

    by_id = {row["export_id"]: row for row in rows}
    assert str(caller_export.export_id) in by_id
    assert str(legacy_caller_export.export_id) in by_id
    assert str(other_org_export.export_id) not in by_id

    for export in [caller_export, legacy_caller_export]:
        row = by_id[str(export.export_id)]
        assert set(["export_id", "incident_id", "status", "created_at_utc"]).issubset(
            row.keys()
        )
        assert row["incident_id"] == str(export.incident_id)
        assert row["status"] == export.status
        assert row["created_at_utc"] is not None


def test_list_exports_regression_excludes_exports_from_unauthorized_org(
    client: TestClient,
    db_session,
    other_org,
    auth_headers,
) -> None:
    other_incident = Incident(org_id=other_org.id, status="open")
    db_session.add(other_incident)
    db_session.commit()
    db_session.refresh(other_incident)

    unauthorized_export = Export(
        incident_id=other_incident.incident_id,
        org_id=other_org.id,
        status="requested",
    )
    db_session.add(unauthorized_export)
    db_session.commit()

    response = client.get("/exports/", headers=auth_headers)
    assert response.status_code == 200
    rows = response.json()
    assert rows == []
