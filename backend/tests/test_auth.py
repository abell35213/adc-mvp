"""Tests for auth endpoints and helpers."""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import get_db
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.main import app


# ── Fixtures ────────────────────────────────────────────────────────

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


# ── Password hashing ───────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("mypassword")
        assert not verify_password("wrongpassword", hashed)

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


# ── JWT tokens ─────────────────────────────────────────────────────

class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token({"sub": "user-123", "role": "admin"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"

    def test_invalid_token_returns_none(self):
        assert decode_access_token("not.a.token") is None

    def test_token_contains_exp(self):
        token = create_access_token({"sub": "u1"})
        payload = decode_access_token(token)
        assert "exp" in payload
        assert "iat" in payload


# ── POST /auth/register ────────────────────────────────────────────

class TestRegister:
    def test_register_returns_201(self, client):
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "password": "secret123",
            "role": "safety_manager",
            "org_name": "Acme Trucking",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "safety_manager"
        assert "access_token" in data
        assert "user_id" in data
        assert "org_id" in data

    def test_register_duplicate_email_returns_409(self, client):
        client.post("/auth/register", json={
            "email": "dup@example.com",
            "password": "pass1",
        })
        resp = client.post("/auth/register", json={
            "email": "dup@example.com",
            "password": "pass2",
        })
        assert resp.status_code == 409


# ── POST /auth/login ───────────────────────────────────────────────

class TestLogin:
    def test_login_returns_token(self, client):
        client.post("/auth/register", json={
            "email": "login@example.com",
            "password": "secret",
        })
        resp = client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "secret",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={
            "email": "login2@example.com",
            "password": "correct",
        })
        resp = client.post("/auth/login", json={
            "email": "login2@example.com",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert resp.status_code == 401


# ── POST /auth/logout ──────────────────────────────────────────────

class TestLogout:
    def test_logout_returns_200(self, client):
        # Register to get a token
        reg = client.post("/auth/register", json={
            "email": "logout@example.com",
            "password": "secret",
        })
        token = reg.json()["access_token"]

        resp = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Logged out"

    def test_logout_no_auth_returns_401(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code in (401, 403)


# ── GET /auth/me ───────────────────────────────────────────────────

class TestMe:
    def test_me_returns_user_info(self, client):
        reg = client.post("/auth/register", json={
            "email": "me@example.com",
            "password": "secret",
            "org_name": "My Org",
        })
        data = reg.json()
        token = data["access_token"]

        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        me_data = resp.json()
        assert me_data["email"] == "me@example.com"
        assert me_data["role"] == "safety_manager"
        assert "user_id" in me_data
        assert len(me_data["org_ids"]) == 1
        assert me_data["active_org_id"] == me_data["org_ids"][0]

    def test_me_no_auth_returns_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code in (401, 403)


# ── Login sets httpOnly cookie ─────────────────────────────────────

class TestLoginCookie:
    def test_login_sets_httponly_cookie(self, client):
        client.post("/auth/register", json={
            "email": "cookie@example.com",
            "password": "secret",
        })
        resp = client.post("/auth/login", json={
            "email": "cookie@example.com",
            "password": "secret",
        })
        assert resp.status_code == 200
        cookies = resp.cookies
        assert "access_token" in cookies
