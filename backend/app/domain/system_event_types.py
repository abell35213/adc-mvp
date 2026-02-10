"""System event type definitions.

Every claim is backed by a timestamped system event.
These types form the contract for the append-only event log.
"""

from enum import Enum


class SystemEventType(str, Enum):
    """Strict set of system event types for the append-only event log."""

    # ── Incident lifecycle ──────────────────────────────────────────
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

    # ── Driver OTP ─────────────────────────────────────────────────
    DRIVER_OTP_REQUESTED = "driver_otp_requested"
    DRIVER_OTP_VERIFIED = "driver_otp_verified"
    DRIVER_OTP_FAILED = "driver_otp_failed"
