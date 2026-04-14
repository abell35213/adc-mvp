"""Onboarding progress primitives and step derivation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.onboarding.models import ReadinessStep, ReadinessStepStatus


@dataclass(slots=True)
class OnboardingSignals:
    """Normalized onboarding signals used by readiness orchestration."""

    org_settings_configured: bool = False
    org_admin_count: int = 0
    safety_capable_user_count: int = 0
    active_user_count: int = 0
    successful_import_count: int = 0
    failed_import_count: int = 0
    successful_driver_import_count: int = 0
    failed_driver_import_count: int = 0
    mapping_count: int = 0
    active_integration_count: int = 0
    total_integration_count: int = 0
    vehicles_total: int = 0
    qr_codes_generated: int = 0
    qr_codes_activated: int = 0
    last_qr_rotation_at_utc: datetime | None = None
    protocol_configured: bool = False
    test_run_passed: bool = False
    export_validation_passed: bool = False
    has_started_activity: bool = False


@dataclass(slots=True)
class StepDefinition:
    key: str
    label: str
    order: int


STEP_DEFINITIONS: tuple[StepDefinition, ...] = (
    StepDefinition("org_settings", "Organization basics", 10),
    StepDefinition("users_roles", "Users and roles", 20),
    StepDefinition("imports", "Data imports", 30),
    StepDefinition("driversImported", "Drivers imported", 35),
    StepDefinition("mappings", "External mappings", 40),
    StepDefinition("integrations", "Integrations", 50),
    StepDefinition("vehicle_qr", "Vehicle QR deployment", 60),
    StepDefinition("driver_protocol", "Driver protocol", 70),
    StepDefinition("test_run", "Test incident run", 80),
    StepDefinition("export_validation", "Export validation", 90),
)


def derive_step_statuses(
    *, signals: OnboardingSignals, blocked_step_keys: set[str]
) -> list[ReadinessStep]:
    """Derive step-level readiness status from normalized onboarding signals."""
    statuses: dict[str, ReadinessStepStatus] = {
        "org_settings": "completed"
        if signals.org_settings_configured
        else "not_started",
        "users_roles": "completed"
        if signals.org_admin_count > 0 and signals.safety_capable_user_count > 0
        else "in_progress"
        if signals.active_user_count > 0
        else "not_started",
        "imports": "completed"
        if signals.successful_import_count > 0 and signals.failed_import_count == 0
        else "in_progress"
        if signals.successful_import_count > 0 or signals.failed_import_count > 0
        else "not_started",
        "driversImported": "completed"
        if signals.successful_driver_import_count > 0
        and signals.failed_driver_import_count == 0
        else "in_progress"
        if signals.successful_driver_import_count > 0
        or signals.failed_driver_import_count > 0
        else "not_started",
        "mappings": "completed" if signals.mapping_count > 0 else "not_started",
        "integrations": "completed"
        if signals.active_integration_count > 0
        else "in_progress"
        if signals.total_integration_count > 0
        else "not_started",
        "vehicle_qr": "completed"
        if signals.vehicles_total > 0
        and signals.qr_codes_activated >= signals.vehicles_total
        else "in_progress"
        if signals.qr_codes_generated > 0
        else "not_started",
        "driver_protocol": "completed"
        if signals.protocol_configured
        else "not_started",
        "test_run": "completed" if signals.test_run_passed else "not_started",
        "export_validation": "completed"
        if signals.export_validation_passed
        else "not_started",
    }

    steps: list[ReadinessStep] = []
    for definition in STEP_DEFINITIONS:
        status = (
            "blocked"
            if definition.key in blocked_step_keys
            else statuses[definition.key]
        )
        steps.append(
            ReadinessStep(
                key=definition.key,
                label=definition.label,
                status=status,
                order=definition.order,
                metadata={},
            )
        )
    return steps


def completion_percent(steps: list[ReadinessStep]) -> int:
    if not steps:
        return 0
    completed = sum(1 for step in steps if step.status == "completed")
    return int((completed / len(steps)) * 100)


def completed_step_keys(steps: list[ReadinessStep]) -> set[str]:
    return {step.key for step in steps if step.status == "completed"}
