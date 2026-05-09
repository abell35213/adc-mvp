"""Tests for SystemEventType enum."""

from app.api.schemas import EventSummary
from app.domain.system_event_types import SystemEventType


class TestSystemEventType:
    """Validate the SystemEventType contract."""

    def test_total_count(self):
        """There must be exactly 69 system event types."""
        assert len(SystemEventType) == 69

    def test_is_str_enum(self):
        """Every member must be usable as a plain string."""
        for member in SystemEventType:
            assert isinstance(member, str)
            assert member == member.value

    # ── Incident lifecycle ──────────────────────────────────────────

    def test_incident_protocol_initiated(self):
        assert (
            SystemEventType.INCIDENT_PROTOCOL_INITIATED == "incident_protocol_initiated"
        )

    def test_incident_started(self):
        assert SystemEventType.INCIDENT_STARTED == "incident_started"

    def test_incident_updated(self):
        assert SystemEventType.INCIDENT_UPDATED == "incident_updated"

    def test_evidence_lockdown_started(self):
        assert SystemEventType.EVIDENCE_LOCKDOWN_STARTED == "evidence_lockdown_started"

    # ── Evidence capture tasks ──────────────────────────────────────

    def test_evidence_capture_requested(self):
        assert (
            SystemEventType.EVIDENCE_CAPTURE_REQUESTED == "evidence_capture_requested"
        )

    def test_evidence_capture_attempted(self):
        assert (
            SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED == "evidence_capture_attempted"
        )

    def test_evidence_capture_succeeded(self):
        assert (
            SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED == "evidence_capture_succeeded"
        )

    def test_evidence_capture_failed(self):
        assert SystemEventType.EVIDENCE_CAPTURE_FAILED == "evidence_capture_failed"

    def test_mcmis_inspections_fetched(self):
        assert (
            SystemEventType.MCMIS_INSPECTIONS_FETCHED == "mcmis_inspections_fetched"
        )

    def test_weather_snapshot_requested(self):
        assert (
            SystemEventType.WEATHER_SNAPSHOT_REQUESTED
            == "weather_snapshot_requested"
        )

    def test_weather_snapshot_captured(self):
        assert SystemEventType.WEATHER_SNAPSHOT_CAPTURED == "weather_snapshot_captured"

    def test_weather_snapshot_failed(self):
        assert SystemEventType.WEATHER_SNAPSHOT_FAILED == "weather_snapshot_failed"

    def test_weather_map_snapshot_requested(self):
        assert (
            SystemEventType.WEATHER_MAP_SNAPSHOT_REQUESTED
            == "weather_map_snapshot_requested"
        )

    def test_weather_map_snapshot_captured(self):
        assert (
            SystemEventType.WEATHER_MAP_SNAPSHOT_CAPTURED
            == "weather_map_snapshot_captured"
        )

    def test_weather_map_snapshot_failed(self):
        assert (
            SystemEventType.WEATHER_MAP_SNAPSHOT_FAILED
            == "weather_map_snapshot_failed"
        )

    # ── Artifacts ───────────────────────────────────────────────────

    def test_artifact_recorded(self):
        assert SystemEventType.ARTIFACT_RECORDED == "artifact_recorded"

    def test_artifact_hashed(self):
        assert SystemEventType.ARTIFACT_HASHED == "artifact_hashed"

    def test_artifact_accessed(self):
        assert SystemEventType.ARTIFACT_ACCESSED == "artifact_accessed"

    def test_artifact_downloaded(self):
        assert SystemEventType.ARTIFACT_DOWNLOADED == "artifact_downloaded"

    # ── Exports ─────────────────────────────────────────────────────

    def test_export_requested(self):
        assert SystemEventType.EXPORT_REQUESTED == "export_requested"

    def test_export_generated(self):
        assert SystemEventType.EXPORT_GENERATED == "export_generated"

    def test_export_retry_requested(self):
        assert SystemEventType.EXPORT_RETRY_REQUESTED == "export_retry_requested"

    def test_export_queued(self):
        assert SystemEventType.EXPORT_QUEUED == "export_queued"

    def test_export_processing_started(self):
        assert (
            SystemEventType.EXPORT_PROCESSING_STARTED == "export_processing_started"
        )

    def test_export_section_generated(self):
        assert SystemEventType.EXPORT_SECTION_GENERATED == "export_section_generated"

    def test_export_package_uploaded(self):
        assert SystemEventType.EXPORT_PACKAGE_UPLOADED == "export_package_uploaded"

    def test_export_failed(self):
        assert SystemEventType.EXPORT_FAILED == "export_failed"

    def test_export_downloaded(self):
        assert SystemEventType.EXPORT_DOWNLOADED == "export_downloaded"

    # ── Notifications ───────────────────────────────────────────────

    def test_safety_manager_sms_sent(self):
        assert SystemEventType.SAFETY_MANAGER_SMS_SENT == "safety_manager_sms_sent"

    def test_safety_manager_sms_failed(self):
        assert SystemEventType.SAFETY_MANAGER_SMS_FAILED == "safety_manager_sms_failed"

    def test_safety_manager_call_placed(self):
        assert (
            SystemEventType.SAFETY_MANAGER_CALL_PLACED == "safety_manager_call_placed"
        )

    def test_safety_manager_call_failed(self):
        assert (
            SystemEventType.SAFETY_MANAGER_CALL_FAILED == "safety_manager_call_failed"
        )

    # ── Grouping helpers ────────────────────────────────────────────

    def test_incident_lifecycle_types_exist(self):
        """All incident lifecycle types must be present."""
        expected = {
            "incident_protocol_initiated",
            "incident_started",
            "incident_updated",
            "evidence_lockdown_started",
            "incident_owner_assigned",
            "incident_owner_reassigned",
            "incident_owner_cleared",
            "incident_status_changed",
            "incident_status_escalated",
            "incident_status_closed",
            "incident_status_reopened",
            "incident_note_added",
            "incident_note_edited",
            "incident_note_deleted",
            "incident_task_created",
            "incident_task_completed",
            "incident_task_cancelled",
            "incident_task_reassigned",
            "incident_readiness_override_set",
            "incident_readiness_override_cleared",
        }
        values = {m.value for m in SystemEventType}
        assert expected.issubset(values)

    def test_evidence_capture_types_exist(self):
        """All evidence capture types must be present."""
        expected = {
            "evidence_capture_requested",
            "evidence_capture_attempted",
            "evidence_capture_succeeded",
            "evidence_capture_failed",
        }
        values = {m.value for m in SystemEventType}
        assert expected.issubset(values)

    def test_weather_capture_types_exist(self):
        """All weather snapshot capture types must be present."""
        expected = {
            "weather_snapshot_requested",
            "weather_snapshot_captured",
            "weather_snapshot_failed",
            "weather_map_snapshot_requested",
            "weather_map_snapshot_captured",
            "weather_map_snapshot_failed",
        }
        values = {m.value for m in SystemEventType}
        assert expected.issubset(values)

    def test_artifact_types_exist(self):
        """All artifact types must be present."""
        expected = {
            "artifact_recorded",
            "artifact_hashed",
            "artifact_accessed",
            "artifact_downloaded",
        }
        values = {m.value for m in SystemEventType}
        assert expected.issubset(values)

    def test_export_types_exist(self):
        """All export types must be present."""
        expected = {
            "export_requested",
            "export_retry_requested",
            "export_queued",
            "export_processing_started",
            "export_section_generated",
            "export_package_uploaded",
            "export_generated",
            "export_failed",
            "export_downloaded",
        }
        values = {m.value for m in SystemEventType}
        assert expected.issubset(values)

    def test_notification_types_exist(self):
        """All notification types must be present."""
        expected = {
            "safety_manager_sms_sent",
            "safety_manager_sms_failed",
            "safety_manager_call_placed",
            "safety_manager_call_failed",
        }
        values = {m.value for m in SystemEventType}
        assert expected.issubset(values)

    def test_no_duplicate_values(self):
        """No two members should share the same value."""
        values = [m.value for m in SystemEventType]
        assert len(values) == len(set(values))

    def test_event_summary_accepts_new_event_types_without_schema_change(self):
        """Timeline schema remains tolerant because event_type is free-form text."""
        event = EventSummary(
            occurred_at_utc="2026-01-01T00:00:00Z",
            event_type=SystemEventType.WEATHER_MAP_SNAPSHOT_CAPTURED,
            actor_type="system",
            payload={"detail": "Weather map snapshot saved."},
        )
        assert event.event_type == "weather_map_snapshot_captured"
