"""Typed onboarding models for launch readiness and setup workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

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
    qr_codes_activated: int
    last_rotated_at_utc: datetime | None = None


@dataclass(slots=True)
class TestIncidentRun:
    status: IncidentRunStatus
    incident_id: str | None = None
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    findings: list[str] = field(default_factory=list)


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
    snapshot_created_at_utc: datetime | None = None
