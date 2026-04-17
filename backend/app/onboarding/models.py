"""Typed onboarding models for launch readiness and setup workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
import uuid

ReadinessStatus = Literal[
    "not_started",
    "in_progress",
    "pilot_ready",
    "launch_ready",
    "blocked",
]
ReadinessStepStatus = Literal["not_started", "in_progress", "completed", "blocked"]
ImportJobStatus = Literal["pending", "running", "succeeded", "failed"]
ValidationSeverity = Literal["info", "warning", "error"]
QrDeploymentStatus = Literal["not_started", "in_progress", "completed", "blocked"]
IncidentRunStatus = Literal["not_started", "in_progress", "completed", "blocked"]


@dataclass(slots=True)
class ReadinessStep:
    key: str
    label: str
    status: ReadinessStepStatus
    order: int
    completed_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ReadinessBlocker:
    code: str
    title: str
    detail: str
    severity: ValidationSeverity
    blocking_step_key: str | None = None
    created_at_utc: datetime | None = None
    resolved_at_utc: datetime | None = None
    is_resolved: bool = False


@dataclass(slots=True)
class ImportJob:
    import_job_id: str
    provider: str
    status: ImportJobStatus
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    records_total: int = 0
    records_succeeded: int = 0
    records_failed: int = 0
    error_message: str | None = None


@dataclass(slots=True)
class IntegrationValidationResult:
    integration_key: str
    status: ReadinessStepStatus
    checked_at_utc: datetime
    detail: str
    severity: ValidationSeverity = "info"
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VehicleQrDeployment:
    status: QrDeploymentStatus
    vehicles_total: int
    qr_codes_generated: int
    qr_codes_distributed: int
    qr_codes_confirmed: int
    last_rotated_at_utc: datetime | None = None
    coverage_blockers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TestIncidentRun:
    status: IncidentRunStatus
    run_id: uuid.UUID | None = None
    incident_id: str | None = None
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    step_results: list[dict[str, object]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExportValidationRun:
    status: IncidentRunStatus
    validation_run_id: uuid.UUID | None = None
    export_id: uuid.UUID | None = None
    incident_id: str | None = None
    validated_at_utc: datetime | None = None
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[dict[str, str]] = field(default_factory=list)
    missing_items: list[dict[str, str]] = field(default_factory=list)
    details: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class OnboardingMetricsSnapshot:
    onboarding_started_at_utc: datetime | None = None
    latest_activity_at_utc: datetime | None = None
    time_to_pilot_ready_hours: float | None = None
    time_to_launch_ready_hours: float | None = None
    import_success_rate: float = 0.0
    driver_import_success_rate: float = 0.0
    qr_coverage_rate: float = 0.0
    valid_driver_phone_ratio: float = 0.0
    integration_validation_pass_rate: float = 0.0
    sample_incident_completion_rate: float = 0.0
    export_validation_rate: float = 0.0
    common_blockers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OnboardingAlertCondition:
    code: str
    title: str
    severity: ValidationSeverity
    triggered: bool
    detail: str


@dataclass(slots=True)
class ProtocolSetupStep:
    instruction_set_selected: bool
    instruction_source: str
    safety_contact_configured: bool
    safety_manager_phone: str | None
    required_media_prompts_defaulted: bool
    export_profile_defaulted: bool
    export_profiles_available: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OrgLaunchReadiness:
    org_id: str
    status: ReadinessStatus
    percent_complete: int
    steps: list[ReadinessStep] = field(default_factory=list)
    blockers: list[ReadinessBlocker] = field(default_factory=list)
    import_jobs: list[ImportJob] = field(default_factory=list)
    integration_validations: list[IntegrationValidationResult] = field(
        default_factory=list
    )
    vehicle_qr_deployment: VehicleQrDeployment | None = None
    test_incident_run: TestIncidentRun | None = None
    latest_export_validation: ExportValidationRun | None = None
    metrics: OnboardingMetricsSnapshot | None = None
    alert_conditions: list[OnboardingAlertCondition] = field(default_factory=list)
    reporting_hooks: dict[str, object] = field(default_factory=dict)
    snapshot_created_at_utc: datetime | None = None
