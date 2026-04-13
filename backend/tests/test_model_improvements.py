"""Tests for SQLAlchemy model improvements (foreign keys, enums, timestamps, indexes)."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Artifact,
    Base,
    CaseNote,
    CaseReadinessOverride,
    CaseTask,
    Event,
    Export,
    Incident,
    Org,
)


@pytest.fixture
def db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


class TestForeignKeyConstraints:
    """Test foreign key constraints are working."""

    def test_event_incident_foreign_key_enforced(self, db):
        """Event.incident_id must reference a valid Incident."""
        # Try to create event with non-existent incident_id
        # This should raise IntegrityError due to foreign key constraint
        invalid_incident_id = uuid.uuid4()
        event = Event(
            incident_id=invalid_incident_id,
            event_type="test_event",
            actor_type="system",
            actor_id="test",
        )
        db.add(event)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_artifact_incident_foreign_key_enforced(self, db):
        """Artifact.incident_id must reference a valid Incident."""
        # Try to create artifact with non-existent incident_id
        # This should raise IntegrityError due to foreign key constraint
        invalid_incident_id = uuid.uuid4()
        artifact = Artifact(
            incident_id=invalid_incident_id,
            artifact_type="dashcam_video",
            status="pending",
        )
        db.add(artifact)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_export_incident_foreign_key_enforced(self, db):
        """Export.incident_id must reference a valid Incident."""
        # Try to create export with non-existent incident_id
        # This should raise IntegrityError due to foreign key constraint
        invalid_incident_id = uuid.uuid4()
        export = Export(
            incident_id=invalid_incident_id,
            status="requested",
        )
        db.add(export)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_case_note_incident_foreign_key_enforced(self, db):
        """CaseNote.incident_id must reference a valid Incident."""
        invalid_incident_id = uuid.uuid4()
        note = CaseNote(incident_id=invalid_incident_id, body="Internal note")
        db.add(note)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_foreign_key_allows_valid_incident(self, db):
        """Foreign key constraints allow valid incident references."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        # These should all succeed with valid incident_id
        event = Event(
            incident_id=incident.incident_id,
            event_type="test_event",
            actor_type="system",
            actor_id="test",
        )
        artifact = Artifact(
            incident_id=incident.incident_id,
            artifact_type="dashcam_video",
            status="pending",
        )
        export = Export(
            incident_id=incident.incident_id,
            status="requested",
        )
        db.add_all([event, artifact, export])
        db.commit()

        assert event.incident_id == incident.incident_id
        assert artifact.incident_id == incident.incident_id
        assert export.incident_id == incident.incident_id


class TestStatusEnums:
    """Test status field enum constraints."""

    def test_incident_status_valid_values(self, db):
        """Incident status accepts valid enum values."""
        org = Org(name="Test Org")
        db.add(org)
        db.commit()

        # Test all valid status values
        for status in ["open", "evidence_capturing", "closed"]:
            incident = Incident(status=status, org_id=org.id)
            db.add(incident)
            db.commit()
            assert incident.status == status

    def test_incident_case_status_valid_values(self, db):
        """Incident case_status accepts valid enum values."""
        org = Org(name="Test Org")
        db.add(org)
        db.commit()

        valid_case_statuses = [
            "new",
            "in_review",
            "awaiting_evidence",
            "awaiting_follow_up",
            "ready_for_export",
            "exported",
            "escalated",
            "closed",
        ]
        for case_status in valid_case_statuses:
            incident = Incident(status="open", case_status=case_status, org_id=org.id)
            db.add(incident)
            db.commit()
            assert incident.case_status == case_status

    def test_artifact_status_valid_values(self, db):
        """Artifact status accepts valid enum values."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        # Test all valid status values
        for status in ["pending", "captured", "unavailable"]:
            artifact = Artifact(
                incident_id=incident.incident_id,
                artifact_type="dashcam_video",
                status=status,
            )
            db.add(artifact)
            db.commit()
            assert artifact.status == status

    def test_export_status_valid_values(self, db):
        """Export status accepts valid enum values."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        # Test all valid status values
        for status in ["requested", "queued", "processing", "ready", "failed", "expired"]:
            export = Export(
                incident_id=incident.incident_id,
                status=status,
            )
            db.add(export)
            db.commit()
            assert export.status == status


class TestTimestamps:
    """Test created_at_utc timestamps."""

    def test_event_has_created_at_utc(self, db):
        """Event model has created_at_utc field."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        event = Event(
            incident_id=incident.incident_id,
            event_type="test_event",
            actor_type="system",
            actor_id="test",
        )
        db.add(event)
        db.commit()

        assert hasattr(event, "created_at_utc")
        assert event.created_at_utc is not None
        assert isinstance(event.created_at_utc, datetime)

    def test_artifact_has_created_at_utc(self, db):
        """Artifact model has created_at_utc field."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        artifact = Artifact(
            incident_id=incident.incident_id,
            artifact_type="dashcam_video",
            status="pending",
        )
        db.add(artifact)
        db.commit()

        assert hasattr(artifact, "created_at_utc")
        assert artifact.created_at_utc is not None
        assert isinstance(artifact.created_at_utc, datetime)


class TestCompositeIndexes:
    """Test that composite indexes are defined (structure tests)."""

    def test_event_has_composite_indexes(self):
        """Event model has composite indexes defined."""
        # Check that __table_args__ exists and has Index definitions
        assert hasattr(Event, "__table_args__")
        table_args = Event.__table_args__
        assert isinstance(table_args, tuple)
        assert len(table_args) >= 2  # At least 2 indexes

        # Extract index names
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]
        assert "ix_events_org_incident" in index_names
        assert "ix_events_org_type_occurred" in index_names

    def test_artifact_has_composite_indexes(self):
        """Artifact model has composite indexes defined."""
        assert hasattr(Artifact, "__table_args__")
        table_args = Artifact.__table_args__
        assert isinstance(table_args, tuple)

        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]
        assert "ix_artifacts_org_incident" in index_names
        assert "ix_artifacts_incident_type" in index_names

    def test_export_has_composite_indexes(self):
        """Export model has composite indexes defined."""
        assert hasattr(Export, "__table_args__")
        table_args = Export.__table_args__
        assert isinstance(table_args, tuple)

        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]
        assert "ix_exports_org_incident" in index_names

    def test_incident_has_case_management_indexes(self):
        """Incident model has case queue indexes defined."""
        assert hasattr(Incident, "__table_args__")
        table_args = Incident.__table_args__
        assert isinstance(table_args, tuple)

        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]
        assert "ix_incidents_org_case_status_owner" in index_names
        assert "ix_incidents_org_readiness_state" in index_names
        assert "ix_incidents_org_updated_at_utc" in index_names
        assert "ix_incidents_org_last_activity_at_utc" in index_names

    def test_case_task_has_overdue_index(self):
        """CaseTask model has overdue query index defined."""
        assert hasattr(CaseTask, "__table_args__")
        table_args = CaseTask.__table_args__
        assert isinstance(table_args, tuple)

        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]
        assert "ix_case_tasks_org_status_due_at_utc" in index_names


class TestDefaultValues:
    """Test default values work correctly."""

    def test_incident_default_status_is_open(self, db):
        """Incident defaults to 'open' status."""
        org = Org(name="Test Org")
        db.add(org)
        db.commit()

        incident = Incident(org_id=org.id)
        db.add(incident)
        db.commit()
        assert incident.status == "open"
        assert incident.case_status == "new"

    def test_artifact_default_status_is_pending(self, db):
        """Artifact defaults to 'pending' status."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        artifact = Artifact(
            incident_id=incident.incident_id,
            artifact_type="dashcam_video",
        )
        db.add(artifact)
        db.commit()
        assert artifact.status == "pending"

    def test_export_default_status_is_requested(self, db):
        """Export defaults to 'requested' status."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        export = Export(incident_id=incident.incident_id)
        db.add(export)
        db.commit()
        assert export.status == "requested"

    def test_case_task_defaults(self, db):
        """CaseTask defaults status, type, and priority values."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        task = CaseTask(incident_id=incident.incident_id, title="Collect witness statement")
        db.add(task)
        db.commit()

        assert task.status == "open"
        assert task.task_type == "other"
        assert task.priority == "medium"

    def test_case_note_soft_delete_defaults(self, db):
        """CaseNote defaults to non-deleted state."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        note = CaseNote(incident_id=incident.incident_id, body="Hidden internal note")
        db.add(note)
        db.commit()

        assert note.is_deleted is False

    def test_case_readiness_override_persists(self, db):
        """CaseReadinessOverride persists manual override snapshots."""
        org = Org(name="Test Org")
        incident = Incident(status="open", org_id=org.id)
        db.add_all([org, incident])
        db.commit()

        override = CaseReadinessOverride(
            incident_id=incident.incident_id,
            reason="Investigator approved manual readiness override.",
            readiness_state="ready",
            completeness_percent=100,
            completeness_status="complete",
        )
        db.add(override)
        db.commit()

        assert override.reason.startswith("Investigator")
        assert override.completeness_percent == 100
