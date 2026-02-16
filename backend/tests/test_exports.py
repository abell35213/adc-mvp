"""Basic test cases for the export API endpoints.

This module contains simple unit tests to exercise the new export
listing functionality. These tests are not exhaustive but
demonstrate how pytest can be used to drive the FastAPI app and
assert responses. To execute the tests, run ``pytest`` from the
repository root.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

try:
    from app.main import app
    from app.db.models import Base, User, Org, UserOrg
    from app.db.session import get_db
    from app.core.security import hash_password, create_access_token
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
    """Ensure the list exports endpoint returns an empty list when no exports exist."""
    response = client.get("/api/exports", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []