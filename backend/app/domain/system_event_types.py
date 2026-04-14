"""System event type definitions.

Every claim is backed by a timestamped system event.
These types form the contract for the append-only event log.
"""

from enum import Enum


class SystemEventType(str, Enum):
    """Strict set of system event types for the append-only event log."""

    # ── Incident lifecycle ──────────────────────────────────────────
    INCIDENT_PROTOCOL_INITIATED = "incident_protocol_initiated"
    INCIDENT_STARTED = "incident_started"
    INCIDENT_UPDATED = "incident_updated"
    EVIDENCE_LOCKDOWN_STARTED = "evidence_lockdown_started"
    INCIDENT_OWNER_ASSIGNED = "incident_owner_assigned"
    INCIDENT_OWNER_REASSIGNED = "incident_owner_reassigned"
    INCIDENT_OWNER_CLEARED = "incident_owner_cleared"
    INCIDENT_STATUS_CHANGED = "incident_status_changed"
    INCIDENT_STATUS_ESCALATED = "incident_status_escalated"
    INCIDENT_STATUS_CLOSED = "incident_status_closed"
    INCIDENT_STATUS_REOPENED = "incident_status_reopened"
    INCIDENT_NOTE_ADDED = "incident_note_added"
    INCIDENT_NOTE_EDITED = "incident_note_edited"
    INCIDENT_NOTE_DELETED = "incident_note_deleted"
    INCIDENT_TASK_CREATED = "incident_task_created"
    INCIDENT_TASK_COMPLETED = "incident_task_completed"
    INCIDENT_TASK_CANCELLED = "incident_task_cancelled"
    INCIDENT_TASK_REASSIGNED = "incident_task_reassigned"
    INCIDENT_READINESS_OVERRIDE_SET = "incident_readiness_override_set"
    INCIDENT_READINESS_OVERRIDE_CLEARED = "incident_readiness_override_cleared"

    # ── Evidence capture tasks ──────────────────────────────────────
    EVIDENCE_CAPTURE_REQUESTED = "evidence_capture_requested"
    EVIDENCE_CAPTURE_ATTEMPTED = "evidence_capture_attempted"
    EVIDENCE_CAPTURE_SUCCEEDED = "evidence_capture_succeeded"
    EVIDENCE_CAPTURE_FAILED = "evidence_capture_failed"

    # ── Artifacts ───────────────────────────────────────────────────
    ARTIFACT_RECORDED = "artifact_recorded"
    ARTIFACT_HASHED = "artifact_hashed"
    ARTIFACT_ACCESSED = "artifact_accessed"
    ARTIFACT_DOWNLOADED = "artifact_downloaded"

    # ── Exports ─────────────────────────────────────────────────────
    EXPORT_REQUESTED = "export_requested"
    EXPORT_RETRY_REQUESTED = "export_retry_requested"
    EXPORT_QUEUED = "export_queued"
    EXPORT_PROCESSING_STARTED = "export_processing_started"
    EXPORT_SECTION_GENERATED = "export_section_generated"
    EXPORT_PACKAGE_UPLOADED = "export_package_uploaded"
    EXPORT_GENERATED = "export_generated"
    EXPORT_FAILED = "export_failed"
    EXPORT_DOWNLOADED = "export_downloaded"

    # ── Driver / Vehicle QR ────────────────────────────────────────
    DRIVER_VEHICLE_RESOLVED = "driver_vehicle_resolved"
    DRIVER_INSTRUCTION_ACKNOWLEDGED = "driver_instruction_acknowledged"
    DRIVER_PROTOCOL_LAUNCH_CONFIRMED = "driver_protocol_launch_confirmed"
    DRIVER_SAFETY_GATE_VIEWED = "driver_safety_gate_viewed"
    DRIVER_SAFETY_GATE_ACKNOWLEDGED = "driver_safety_gate_acknowledged"
    DRIVER_INSTRUCTION_STEP_VIEWED = "driver_instruction_step_viewed"
    DRIVER_INSTRUCTION_STEP_ACKNOWLEDGED = "driver_instruction_step_acknowledged"
    DRIVER_SCENE_FACTS_SAVED = "driver_scene_facts_saved"
    DRIVER_PARTIES_SAVED = "driver_parties_saved"
    DRIVER_MEDIA_UPLOADED = "driver_media_uploaded"
    DRIVER_MEDIA_UPLOAD_FAILED = "driver_media_upload_failed"
    DRIVER_NARRATIVE_SAVED = "driver_narrative_saved"
    DRIVER_REPORT_SUBMITTED = "driver_report_submitted"
    VEHICLE_QR_ROTATED = "vehicle_qr_rotated"

    # ── Notifications ───────────────────────────────────────────────
    SAFETY_MANAGER_SMS_SENT = "safety_manager_sms_sent"
    SAFETY_MANAGER_SMS_FAILED = "safety_manager_sms_failed"
    SAFETY_MANAGER_CALL_PLACED = "safety_manager_call_placed"
    SAFETY_MANAGER_CALL_FAILED = "safety_manager_call_failed"

    # ── Identity / MFA ─────────────────────────────────────────────
    MFA_ENROLLMENT_COMPLETED = "mfa_enrollment_completed"
    MFA_CHALLENGE_COMPLETED = "mfa_challenge_completed"
    MFA_DISABLED = "mfa_disabled"
