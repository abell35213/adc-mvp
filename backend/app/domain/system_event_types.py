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
