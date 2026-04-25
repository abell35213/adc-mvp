"""Targeted regression tests for the Q2 2026 bug-fix sweep.

These tests exercise behaviors that previously had no direct coverage and that
were tightened during the bug-fix sweep:

* Refresh-token reuse must revoke the entire session family rather than just the
  one row that was reused.
* Driver session refresh must preserve the original driver UUID in the new
  access-token's ``sub`` claim (it was previously emitted as ``""``).
* ``Export.org_id`` is NOT NULL — both at the model layer and at the
  ``create_export`` repo boundary — and authorization can no longer be bypassed
  by smuggling in a null org.
* ``emit_audit_event(..., critical=True)`` must propagate audit-pipeline
  failures so callers fail closed for compliance-critical events.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.emitter import emit_audit_event
from app.core.security import decode_access_token
from app.db.models import Base, Driver, Export, Incident, Org, RefreshToken, SessionRecord
from app.db.repo.exports import create_export
from app.security.session import (
    create_session,
    rotate_refresh_token,
)


# ── Shared fixtures ─────────────────────────────────────────────────


@pytest.fixture()
def db_session(monkeypatch):
    # SQLite (used in tests) strips timezone info from TIMESTAMP(timezone=True)
    # columns on round-trip. The session helpers compare ``expires_at`` against
    # ``_utcnow()`` which is timezone-aware, so we patch the helper to produce
    # naive UTC datetimes for the duration of these tests; behavior under
    # Postgres in production is unchanged.
    from datetime import datetime as _dt

    monkeypatch.setattr(
        "app.security.session._utcnow",
        lambda: _dt.utcnow(),
    )

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
def org(db_session):
    org = Org(name="BugFix Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def driver(db_session, org):
    driver = Driver(
        org_id=org.id,
        first_name="Test",
        last_name="Driver",
        phone_e164="+15555550100",
        is_active=True,
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)
    return driver


# ── Refresh-token reuse / family revocation ─────────────────────────


class TestRefreshTokenReuse:
    def test_reusing_consumed_refresh_token_revokes_session(self, db_session):
        """A refresh-token reuse must revoke the parent session immediately."""
        _, refresh_value, session_id = create_session(
            db_session,
            user_id=None,
            org_id=uuid.uuid4(),
            client_type="driver_mobile",
            device_descriptor="dev-1",
            token_subject=str(uuid.uuid4()),
            token_claims={"scope": "driver"},
        )

        # First rotation succeeds.
        rotate_refresh_token(
            db_session,
            refresh_token_value=refresh_value,
            token_subject="",
            token_claims={"scope": "driver"},
            expected_client_type="driver_mobile",
            expected_device_descriptor="dev-1",
        )

        # Re-presenting the original (now consumed) refresh token must fail
        # AND must mark the entire session as revoked.
        with pytest.raises(Exception):
            rotate_refresh_token(
                db_session,
                refresh_token_value=refresh_value,
                token_subject="",
                token_claims={"scope": "driver"},
                expected_client_type="driver_mobile",
                expected_device_descriptor="dev-1",
            )

        session = (
            db_session.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .one()
        )
        assert session.revoked_at is not None, "session must be revoked on reuse"

        # All refresh tokens in the family must also be revoked so the attacker
        # cannot pivot to the descendant token chain.
        active_tokens = (
            db_session.query(RefreshToken)
            .filter(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
            .count()
        )
        assert active_tokens == 0, "all refresh tokens in the family must be revoked"


# ── Driver refresh preserves subject ────────────────────────────────


class TestDriverRefreshPreservesSubject:
    def test_refresh_preserves_driver_subject_in_access_token(self, db_session, org):
        driver_id = uuid.uuid4()
        # Initial driver session — subject is the driver UUID.
        access_initial, refresh_value, session_id = create_session(
            db_session,
            user_id=None,
            org_id=org.id,
            client_type="driver_mobile",
            device_descriptor="dev-A",
            token_subject=str(driver_id),
            token_claims={"scope": "driver"},
        )
        initial_payload = decode_access_token(access_initial)
        assert initial_payload is not None
        assert initial_payload["sub"] == str(driver_id)

        # Subject_id must have been persisted on the session row.
        session = (
            db_session.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .one()
        )
        assert session.subject_id == driver_id

        # Refresh — token_subject is intentionally empty (this mirrors the
        # driver refresh route which has no other source of truth for the
        # subject). The refresh helper must fall back to the persisted
        # subject_id on the session.
        access_new, _, _ = rotate_refresh_token(
            db_session,
            refresh_token_value=refresh_value,
            token_subject="",
            token_claims={"scope": "driver"},
            expected_client_type="driver_mobile",
            expected_device_descriptor="dev-A",
        )
        new_payload = decode_access_token(access_new)
        assert new_payload is not None
        assert new_payload["sub"] == str(driver_id), (
            "driver refresh must reuse the original driver UUID, not ''"
        )


# ── Export.org_id is NOT NULL ───────────────────────────────────────


class TestExportOrgIdRequired:
    def test_create_export_rejects_null_org_id(self, db_session, org):
        incident = Incident(status="open", org_id=org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        with pytest.raises(ValueError, match="org_id"):
            create_export(
                db_session,
                incident_id=incident.incident_id,
                org_id=None,  # type: ignore[arg-type]
            )

    def test_export_model_rejects_null_org_id_at_db_layer(self, db_session, org):
        incident = Incident(status="open", org_id=org.id)
        db_session.add(incident)
        db_session.commit()
        db_session.refresh(incident)

        bogus = Export(incident_id=incident.incident_id, org_id=None, status="requested")
        db_session.add(bogus)
        with pytest.raises(sa.exc.IntegrityError):
            db_session.commit()


# ── Audit emitter critical flag ─────────────────────────────────────


class TestAuditEmitterCritical:
    def test_critical_failure_propagates(self, db_session, org):
        with patch("app.audit.emitter.append_event", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError, match="db down"):
                emit_audit_event(
                    db_session,
                    org_id=org.id,
                    actor_type="user",
                    actor_id="abc",
                    action="export.download",
                    event_type="download_succeeded",
                    critical=True,
                )

    def test_non_critical_failure_swallowed(self, db_session, org):
        # Default behavior remains best-effort: no exception escapes.
        with patch("app.audit.emitter.append_event", side_effect=RuntimeError("db down")):
            emit_audit_event(
                db_session,
                org_id=org.id,
                actor_type="user",
                actor_id="abc",
                action="export.download",
                event_type="download_succeeded",
            )
