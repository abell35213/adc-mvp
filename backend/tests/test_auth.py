"""Tests for auth endpoints and helpers."""

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import AuditEvent, Base, Org, User, UserOrg
from app.db.session import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.main import app
from app.core.config import settings


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

    def test_token_signed_with_wrong_secret_returns_none(self):
        token = jwt.encode(
            {"sub": "user-123"},
            "not-the-configured-secret",
            algorithm=settings.JWT_ALGORITHM,
        )

        assert decode_access_token(token) is None

    def test_token_with_unexpected_algorithm_returns_none(self):
        token = jwt.encode(
            {"sub": "user-123"},
            settings.JWT_SECRET_KEY,
            algorithm="HS384",
        )

        assert decode_access_token(token) is None

    def test_token_contains_exp(self):
        token = create_access_token({"sub": "u1"})
        payload = decode_access_token(token)
        assert payload is not None
        assert "exp" in payload
        assert "iat" in payload


# ── POST /auth/register ────────────────────────────────────────────


class TestRegister:
    def test_register_returns_201(self, client):
        resp = client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "secret123",
                "role": "safety_manager",
                "org_name": "Acme Trucking",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "safety_manager"
        assert "access_token" in data
        assert "user_id" in data
        assert "org_id" in data

    def test_register_duplicate_email_returns_409(self, client):
        client.post(
            "/auth/register",
            json={
                "email": "dup@example.com",
                "password": "pass1",
            },
        )
        resp = client.post(
            "/auth/register",
            json={
                "email": "dup@example.com",
                "password": "pass2",
            },
        )
        assert resp.status_code == 409


# ── POST /auth/login ───────────────────────────────────────────────


class TestLogin:
    def test_login_returns_token(self, client, db_session):
        client.post(
            "/auth/register",
            json={
                "email": "login@example.com",
                "password": "secret",
            },
        )
        resp = client.post(
            "/auth/login",
            json={
                "email": "login@example.com",
                "password": "secret",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        audit = db_session.query(AuditEvent).filter(AuditEvent.event_type == "auth_login_succeeded").first()
        assert audit is not None
        assert audit.outcome == "success"

    def test_login_wrong_password(self, client, db_session):
        client.post(
            "/auth/register",
            json={
                "email": "login2@example.com",
                "password": "correct",
            },
        )
        resp = client.post(
            "/auth/login",
            json={
                "email": "login2@example.com",
                "password": "wrong",
            },
        )
        assert resp.status_code == 401
        audit = db_session.query(AuditEvent).filter(AuditEvent.event_type == "auth_login_failed").first()
        assert audit is not None
        assert audit.outcome == "failure"

    def test_login_unknown_email(self, client):
        resp = client.post(
            "/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "whatever",
            },
        )
        assert resp.status_code == 401

    def test_system_admin_login_requires_mfa(self, client, db_session):
        user = User(
            email="sysadmin@example.com",
            password_hash=hash_password("secret"),
            role="system_admin",
            mfa_enabled=False,
        )
        org = Org(name="ADC")
        db_session.add_all([user, org])
        db_session.flush()
        db_session.add(UserOrg(user_id=user.id, org_id=org.id))
        db_session.commit()

        resp = client.post(
            "/auth/login",
            json={"email": "sysadmin@example.com", "password": "secret"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "MFA enrollment required"

    def test_system_admin_login_with_mfa_code_succeeds(self, client, db_session):
        user = User(
            email="sysadmin2@example.com",
            password_hash=hash_password("secret"),
            role="system_admin",
            mfa_enabled=True,
        )
        org = Org(name="ADC")
        db_session.add_all([user, org])
        db_session.flush()
        db_session.add(UserOrg(user_id=user.id, org_id=org.id))
        db_session.commit()

        expected_code = str(user.id.int)[-6:]
        resp = client.post(
            "/auth/login",
            json={
                "email": "sysadmin2@example.com",
                "password": "secret",
                "mfa_code": expected_code,
            },
        )
        assert resp.status_code == 200

    def test_org_admin_mfa_is_configurable(self, client, db_session):
        prior = settings.ORG_ADMIN_MFA_REQUIRED
        settings.ORG_ADMIN_MFA_REQUIRED = True
        try:
            user = User(
                email="orgadmin@example.com",
                password_hash=hash_password("secret"),
                role="org_admin",
                mfa_enabled=False,
            )
            org = Org(name="ADC")
            db_session.add_all([user, org])
            db_session.flush()
            db_session.add(UserOrg(user_id=user.id, org_id=org.id))
            db_session.commit()

            resp = client.post(
                "/auth/login",
                json={"email": "orgadmin@example.com", "password": "secret"},
            )
            assert resp.status_code == 403
            assert resp.json()["detail"] == "MFA enrollment required"
        finally:
            settings.ORG_ADMIN_MFA_REQUIRED = prior


# ── POST /auth/logout ──────────────────────────────────────────────


class TestLogout:
    def test_logout_returns_200(self, client):
        # Register to get a token
        reg = client.post(
            "/auth/register",
            json={
                "email": "logout@example.com",
                "password": "secret",
            },
        )
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
        reg = client.post(
            "/auth/register",
            json={
                "email": "me@example.com",
                "password": "secret",
                "org_name": "My Org",
            },
        )
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
        client.post(
            "/auth/register",
            json={
                "email": "cookie@example.com",
                "password": "secret",
            },
        )
        resp = client.post(
            "/auth/login",
            json={
                "email": "cookie@example.com",
                "password": "secret",
            },
        )
        assert resp.status_code == 200
        cookies = resp.cookies
        assert "access_token" in cookies
        assert "csrf_token" in cookies
        set_cookie_header = ",".join(resp.headers.get_list("set-cookie"))
        assert "HttpOnly" in set_cookie_header
        assert "SameSite=lax" in set_cookie_header


class TestCsrfProtection:
    def test_cookie_authenticated_refresh_requires_csrf_header(self, client):
        client.post(
            "/auth/register",
            json={"email": "csrf-refresh@example.com", "password": "secret"},
        )
        login = client.post(
            "/auth/login",
            json={"email": "csrf-refresh@example.com", "password": "secret"},
        )
        assert login.status_code == 200

        refresh_without_csrf = client.post("/auth/refresh")
        assert refresh_without_csrf.status_code == 403

        refresh_with_invalid_csrf = client.post(
            "/auth/refresh",
            headers={"x-csrf-token": "invalid-token"},
        )
        assert refresh_with_invalid_csrf.status_code == 403

    def test_cookie_authenticated_logout_requires_csrf_header(self, client):
        client.post(
            "/auth/register",
            json={"email": "csrf-logout@example.com", "password": "secret"},
        )
        login = client.post(
            "/auth/login",
            json={"email": "csrf-logout@example.com", "password": "secret"},
        )
        assert login.status_code == 200

        logout_without_csrf = client.post("/auth/logout")
        assert logout_without_csrf.status_code == 403

        csrf_token = client.cookies.get("csrf_token")
        logout_with_csrf = client.post("/auth/logout", headers={"x-csrf-token": csrf_token})
        assert logout_with_csrf.status_code == 200
