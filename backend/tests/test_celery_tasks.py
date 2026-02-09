"""Tests for Celery task implementations.

These tests call the task functions directly (not via Celery) with
all external dependencies mocked so they run in-memory with SQLite.
"""

import hashlib
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Artifact, Base, Event, Export, Incident


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def incident(db_session):
    inc = Incident(status="evidence_capturing", adc_vehicle_id="v1")
    db_session.add(inc)
    db_session.commit()
    db_session.refresh(inc)
    return inc


@pytest.fixture()
def export_row(db_session, incident):
    exp = Export(incident_id=incident.incident_id, status="requested")
    db_session.add(exp)
    db_session.commit()
    db_session.refresh(exp)
    return exp


# ── Celery app config ───────────────────────────────────────────────


class TestCeleryAppConfig:
    def test_acks_late_enabled(self):
        from app.tasks.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True

    def test_reject_on_worker_lost(self):
        from app.tasks.celery_app import celery_app

        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_task_serializer_is_json(self):
        from app.tasks.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"

    def test_task_routes_defined(self):
        from app.tasks.celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert "app.tasks.evidence_tasks.capture_dashcam" in routes
        assert "app.tasks.evidence_tasks.capture_telematics_bundle" in routes
        assert "app.tasks.export_tasks.build_export" in routes


# ── capture_dashcam ─────────────────────────────────────────────────


class TestCaptureDashcam:
    """Test capture_dashcam task logic."""

    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_both_streams_captured(self, MockSamsara, MockS3, mock_get_db, db_session, incident):
        mock_get_db.return_value = db_session
        video_data = b"fake-video-data"

        samsara_inst = MagicMock()
        samsara_inst.fetch_dashcam_stream.return_value = video_data
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://bucket/key"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_dashcam

        result = capture_dashcam(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        assert result["status"] == "captured"
        assert result["type"] == "dashcam"

        # Two streams → two uploads
        assert s3_inst.upload.call_count == 2

        # Check artifacts were inserted
        artifacts = db_session.query(Artifact).filter(
            Artifact.incident_id == incident.incident_id
        ).all()
        assert len(artifacts) == 2
        assert all(a.status == "captured" for a in artifacts)
        assert all(a.sha256 is not None for a in artifacts)

    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_one_stream_unavailable(self, MockSamsara, MockS3, mock_get_db, db_session, incident):
        """When one stream is unavailable the task still succeeds."""
        mock_get_db.return_value = db_session

        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return b"video-bytes"
            return None  # second stream unavailable

        samsara_inst = MagicMock()
        samsara_inst.fetch_dashcam_stream.side_effect = side_effect
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://bucket/key"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_dashcam

        result = capture_dashcam(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        # Task itself succeeds
        assert result["status"] == "captured"

        artifacts = db_session.query(Artifact).filter(
            Artifact.incident_id == incident.incident_id
        ).all()
        assert len(artifacts) == 2
        statuses = {a.status for a in artifacts}
        assert "captured" in statuses
        assert "unavailable" in statuses

    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_both_streams_unavailable(self, MockSamsara, MockS3, mock_get_db, db_session, incident):
        """Even if both streams are unavailable the task succeeds."""
        mock_get_db.return_value = db_session

        samsara_inst = MagicMock()
        samsara_inst.fetch_dashcam_stream.return_value = None
        MockSamsara.return_value = samsara_inst
        MockS3.return_value = MagicMock()

        from app.tasks.evidence_tasks import capture_dashcam

        result = capture_dashcam(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        assert result["status"] == "captured"

        artifacts = db_session.query(Artifact).filter(
            Artifact.incident_id == incident.incident_id
        ).all()
        assert len(artifacts) == 2
        assert all(a.status == "unavailable" for a in artifacts)

    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_emits_capture_requested_and_succeeded(self, MockSamsara, MockS3, mock_get_db, db_session, incident):
        mock_get_db.return_value = db_session

        samsara_inst = MagicMock()
        samsara_inst.fetch_dashcam_stream.return_value = b"data"
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_dashcam

        capture_dashcam(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id
        ).all()
        event_types = [e.event_type for e in events]

        assert "evidence_capture_requested" in event_types
        assert "evidence_capture_succeeded" in event_types
        assert "artifact_recorded" in event_types
        assert "artifact_hashed" in event_types

    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_sha256_is_correct(self, MockSamsara, MockS3, mock_get_db, db_session, incident):
        mock_get_db.return_value = db_session
        video_data = b"test-video-content"

        samsara_inst = MagicMock()
        samsara_inst.fetch_dashcam_stream.return_value = video_data
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_dashcam

        capture_dashcam(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        expected_sha = hashlib.sha256(video_data).hexdigest()
        artifacts = db_session.query(Artifact).filter(
            Artifact.incident_id == incident.incident_id
        ).all()
        for a in artifacts:
            assert a.sha256 == expected_sha


# ── capture_telematics_bundle ───────────────────────────────────────


class TestCaptureTelematicsBundle:
    """Test capture_telematics_bundle task logic."""

    @patch("app.services.schema_validate.validate_payload", return_value=True)
    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_all_datasets_captured(self, MockSamsara, MockS3, mock_get_db, mock_validate, db_session, incident):
        mock_get_db.return_value = db_session

        raw = [{"driverId": "d1", "eldStatus": "on", "time": "t", "vehicleId": "v1"}]

        samsara_inst = MagicMock()
        samsara_inst.get_eld_logs.return_value = raw
        samsara_inst.get_vehicle_locations.return_value = raw
        samsara_inst.get_safety_events.return_value = raw
        samsara_inst.get_vehicle_state.return_value = raw
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_telematics_bundle

        result = capture_telematics_bundle(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        assert result["status"] == "captured"
        assert result["type"] == "telematics"

        # 4 datasets × 3 formats (JSON, CSV, PDF) = 12 artifacts
        artifacts = db_session.query(Artifact).filter(
            Artifact.incident_id == incident.incident_id
        ).all()
        assert len(artifacts) == 12
        assert all(a.status == "captured" for a in artifacts)

    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_dataset_unavailable_doesnt_crash(self, MockSamsara, MockS3, mock_get_db, db_session, incident):
        mock_get_db.return_value = db_session

        samsara_inst = MagicMock()
        samsara_inst.get_eld_logs.side_effect = Exception("API down")
        samsara_inst.get_vehicle_locations.return_value = []
        samsara_inst.get_safety_events.return_value = []
        samsara_inst.get_vehicle_state.return_value = []
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_telematics_bundle

        result = capture_telematics_bundle(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        assert result["status"] == "captured"

        artifacts = db_session.query(Artifact).filter(
            Artifact.incident_id == incident.incident_id
        ).all()
        # 1 unavailable dataset + 3 datasets × 3 formats each = 10 total
        unavailable = [a for a in artifacts if a.status == "unavailable"]
        captured = [a for a in artifacts if a.status == "captured"]
        assert len(unavailable) == 1
        assert len(captured) == 9

    @patch("app.services.schema_validate.validate_payload", return_value=True)
    @patch("app.tasks.evidence_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    @patch("app.services.samsara_client.SamsaraClient")
    def test_emits_events_for_telematics(self, MockSamsara, MockS3, mock_get_db, mock_validate, db_session, incident):
        mock_get_db.return_value = db_session

        samsara_inst = MagicMock()
        samsara_inst.get_eld_logs.return_value = []
        samsara_inst.get_vehicle_locations.return_value = []
        samsara_inst.get_safety_events.return_value = []
        samsara_inst.get_vehicle_state.return_value = []
        MockSamsara.return_value = samsara_inst

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        MockS3.return_value = s3_inst

        from app.tasks.evidence_tasks import capture_telematics_bundle

        capture_telematics_bundle(
            str(incident.incident_id),
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
        )

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id
        ).all()
        event_types = [e.event_type for e in events]

        assert "evidence_capture_requested" in event_types
        assert "evidence_capture_succeeded" in event_types


# ── Backward-compatible alias ───────────────────────────────────────


class TestBackwardCompatAlias:
    def test_capture_telematics_is_alias(self):
        from app.tasks.evidence_tasks import (
            capture_telematics,
            capture_telematics_bundle,
        )

        assert capture_telematics is capture_telematics_bundle

    def test_generate_export_is_alias(self):
        from app.tasks.export_tasks import build_export, generate_export

        assert generate_export is build_export


# ── build_export ────────────────────────────────────────────────────


class TestBuildExport:
    """Test build_export task logic."""

    @patch("app.tasks.export_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    def test_export_generates_zip(self, MockS3, mock_get_db, db_session, incident, export_row):
        mock_get_db.return_value = db_session

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        s3_inst.download.return_value = b"file-content"
        MockS3.return_value = s3_inst

        # Add a captured artifact for the incident
        art = Artifact(
            incident_id=incident.incident_id,
            artifact_type="eld_log",
            status="captured",
            s3_key="incidents/x/telematics/eld.json",
            sha256="abc",
            byte_size=100,
        )
        db_session.add(art)
        db_session.commit()

        from app.tasks.export_tasks import build_export

        result = build_export(
            str(incident.incident_id),
            str(export_row.export_id),
        )

        assert result["status"] == "ready"

        # ZIP was uploaded to S3
        assert s3_inst.upload.call_count >= 1

        # Export row was updated
        updated_export = db_session.query(Export).filter(
            Export.export_id == export_row.export_id
        ).first()
        assert updated_export.status == "ready"
        assert updated_export.s3_key is not None

    @patch("app.tasks.export_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    def test_export_emits_events(self, MockS3, mock_get_db, db_session, incident, export_row):
        mock_get_db.return_value = db_session

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        s3_inst.download.return_value = b""
        MockS3.return_value = s3_inst

        from app.tasks.export_tasks import build_export

        build_export(
            str(incident.incident_id),
            str(export_row.export_id),
        )

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id
        ).all()
        event_types = [e.event_type for e in events]

        assert "export_requested" in event_types
        assert "export_generated" in event_types

    @patch("app.tasks.export_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    def test_export_contains_sha256(self, MockS3, mock_get_db, db_session, incident, export_row):
        mock_get_db.return_value = db_session

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        s3_inst.download.return_value = b""
        MockS3.return_value = s3_inst

        from app.tasks.export_tasks import build_export

        build_export(
            str(incident.incident_id),
            str(export_row.export_id),
        )

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id,
            Event.event_type == "export_generated",
        ).all()
        assert len(events) == 1
        payload = events[0].payload
        assert "sha256" in payload
        assert "byte_size" in payload

    @patch("app.tasks.export_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    def test_export_skips_duplicate_requested_event(self, MockS3, mock_get_db, db_session, incident, export_row):
        """If EXPORT_REQUESTED was already emitted (via API), don't duplicate."""
        mock_get_db.return_value = db_session

        # Pre-emit EXPORT_REQUESTED like the API does
        from app.db.repo.events import create_event

        create_event(
            db_session,
            incident_id=incident.incident_id,
            event_type="export_requested",
            actor_type="system",
            actor_id="api",
            payload={"export_id": str(export_row.export_id)},
        )

        s3_inst = MagicMock()
        s3_inst.upload.return_value = "s3://b/k"
        s3_inst.download.return_value = b""
        MockS3.return_value = s3_inst

        from app.tasks.export_tasks import build_export

        build_export(
            str(incident.incident_id),
            str(export_row.export_id),
        )

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id,
            Event.event_type == "export_requested",
        ).all()
        # Should be exactly 1 (the one from the API, not duplicated)
        assert len(events) == 1

    @patch("app.tasks.export_tasks._get_db")
    @patch("app.services.vault_s3.VaultS3")
    def test_export_failure_emits_failed_event(self, MockS3, mock_get_db, db_session, incident, export_row):
        mock_get_db.return_value = db_session

        # Make S3 upload explode
        s3_inst = MagicMock()
        s3_inst.upload.side_effect = RuntimeError("S3 down")
        s3_inst.download.return_value = b""
        MockS3.return_value = s3_inst

        from app.tasks.export_tasks import build_export

        with pytest.raises(RuntimeError, match="S3 down"):
            build_export(
                str(incident.incident_id),
                str(export_row.export_id),
            )

        events = db_session.query(Event).filter(
            Event.incident_id == incident.incident_id,
            Event.event_type == "export_failed",
        ).all()
        assert len(events) == 1


# ── repo_exports.update_export ──────────────────────────────────────


class TestUpdateExport:
    def test_update_export_status(self, db_session, incident, export_row):
        from app.db.repo.exports import update_export

        updated = update_export(db_session, export_row.export_id, status="ready")
        assert updated.status == "ready"

    def test_update_export_s3_fields(self, db_session, incident, export_row):
        from app.db.repo.exports import update_export

        updated = update_export(
            db_session, export_row.export_id,
            s3_bucket="my-bucket", s3_key="exports/test.zip",
        )
        assert updated.s3_bucket == "my-bucket"
        assert updated.s3_key == "exports/test.zip"

    def test_update_export_not_found(self, db_session):
        from app.db.repo.exports import update_export

        result = update_export(db_session, uuid.uuid4(), status="ready")
        assert result is None


# ── _hash_bytes helper ──────────────────────────────────────────────


class TestHashBytes:
    def test_hash_bytes_correct(self):
        from app.tasks.evidence_tasks import _hash_bytes

        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert _hash_bytes(data) == expected

    def test_hash_bytes_empty(self):
        from app.tasks.evidence_tasks import _hash_bytes

        expected = hashlib.sha256(b"").hexdigest()
        assert _hash_bytes(b"") == expected
