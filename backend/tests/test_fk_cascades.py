"""Tests for foreign key ON DELETE cascade policies."""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.models import (
    Artifact,
    Base,
    Driver,
    Export,
    Incident,
    Org,
    RefreshToken,
    SessionRecord,
    User,
)


@pytest.fixture
def db():
    """In-memory SQLite DB with FK enforcement enabled."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


class TestCascadeOwnedChildren:
    """Test that owned child rows CASCADE when parent is deleted."""

    def test_deleting_incident_cascades_artifacts(self, db):
        """Artifacts belong to incidents; deleting incident should cascade."""
        import uuid

        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        incident = Incident(incident_id=uuid.UUID("11111111-1111-1111-1111-111111111111"), org_id=org.id)
        db.add(incident)
        db.flush()

        artifact = Artifact(
            incident_id=incident.incident_id,
            org_id=org.id,
            artifact_type="photo",
        )
        db.add(artifact)
        db.commit()

        artifact_id = artifact.artifact_id

        # Delete incident
        db.delete(incident)
        db.commit()

        # Artifact should be cascaded
        assert db.get(Artifact, artifact_id) is None

    def test_deleting_session_cascades_refresh_tokens(self, db):
        """Refresh tokens belong to sessions; deleting session should cascade."""
        import uuid

        org = Org(name="Test Org")
        user = User(email="test@example.com", password_hash="hash")
        db.add_all([org, user])
        db.flush()

        session = SessionRecord(
            user_id=user.id,
            org_id=org.id,
            client_type="web",
            refresh_family_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        )
        db.add(session)
        db.flush()

        token = RefreshToken(
            session_id=session.session_id,
            refresh_family_id=session.refresh_family_id,
            token_hash="hash1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(token)
        db.commit()

        token_id = token.token_id

        # Delete session
        db.delete(session)
        db.commit()

        # Token should be cascaded
        assert db.get(RefreshToken, token_id) is None

    def test_refresh_token_cascade_is_recursive(self, db):
        """Deleting a refresh token should cascade to its children (revoke chain)."""
        import uuid

        org = Org(name="Test Org")
        user = User(email="test@example.com", password_hash="hash")
        db.add_all([org, user])
        db.flush()

        session = SessionRecord(
            user_id=user.id,
            org_id=org.id,
            client_type="web",
            refresh_family_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        )
        db.add(session)
        db.flush()

        parent_token = RefreshToken(
            session_id=session.session_id,
            refresh_family_id=session.refresh_family_id,
            token_hash="parent",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(parent_token)
        db.flush()

        child_token = RefreshToken(
            session_id=session.session_id,
            refresh_family_id=session.refresh_family_id,
            parent_token_id=parent_token.token_id,
            token_hash="child",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(child_token)
        db.commit()

        child_id = child_token.token_id

        # Delete parent token
        db.delete(parent_token)
        db.commit()

        # Child should be cascaded (revoke chain)
        assert db.get(RefreshToken, child_id) is None


class TestRestrictTenantRoots:
    """Test that tenant root FKs (org_id) use RESTRICT to block deletion."""

    def test_cannot_delete_org_with_incidents(self, db):
        """Org with incidents should be blocked from deletion (RESTRICT)."""
        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        incident = Incident(org_id=org.id)
        db.add(incident)
        db.commit()

        # Attempt to delete org should fail
        db.delete(org)
        with pytest.raises(Exception) as exc_info:
            db.commit()
        db.rollback()

        # Should be an integrity error (FOREIGN KEY constraint failed on SQLite)
        assert "integrity" in str(exc_info.value).lower() or "foreign" in str(exc_info.value).lower()

    def test_cannot_delete_org_with_exports(self, db):
        """Org with exports should be blocked from deletion (RESTRICT)."""
        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        incident = Incident(org_id=org.id)
        db.add(incident)
        db.flush()

        export = Export(
            org_id=org.id,
            incident_id=incident.incident_id,
            export_type="court_defense",
        )
        db.add(export)
        db.commit()

        # Attempt to delete org should fail
        db.delete(org)
        with pytest.raises(Exception) as exc_info:
            db.commit()
        db.rollback()

        assert "integrity" in str(exc_info.value).lower() or "foreign" in str(exc_info.value).lower()


class TestSetNullSoftReferences:
    """Test that soft reference FKs use SET NULL on parent deletion."""

    def test_deleting_user_nulls_incident_owner(self, db):
        """Incident.owner_user_id should become NULL when user is deleted."""
        org = Org(name="Test Org")
        user = User(email="owner@example.com", password_hash="hash")
        db.add_all([org, user])
        db.flush()

        incident = Incident(org_id=org.id, owner_user_id=user.id)
        db.add(incident)
        db.commit()

        incident_id = incident.incident_id

        # Delete user
        db.delete(user)
        db.commit()

        # Incident should still exist but owner_user_id should be NULL
        db.expire_all()
        reloaded = db.get(Incident, incident_id)
        assert reloaded is not None
        assert reloaded.owner_user_id is None

    def test_deleting_driver_cascades_assignments(self, db):
        """Driver assignments should CASCADE when driver is deleted."""
        from app.db.models import DriverVehicleAssignment

        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        driver = Driver(
            org_id=org.id,
            phone_e164="+15551234567",
            display_name="Test Driver",
        )
        db.add(driver)
        db.flush()

        assignment = DriverVehicleAssignment(
            org_id=org.id,
            driver_id=driver.driver_id,
            adc_vehicle_id="VEH123",
            source="manual",
        )
        db.add(assignment)
        db.commit()

        assignment_id = assignment.assignment_id

        # Delete driver
        db.delete(driver)
        db.commit()

        # Assignment should be cascaded
        assert db.get(DriverVehicleAssignment, assignment_id) is None
