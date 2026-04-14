"""Readiness status derivation for pilot and launch milestones."""

from __future__ import annotations

from app.onboarding.models import ReadinessStatus, ReadinessStep

PILOT_THRESHOLD_PERCENT = 60
LAUNCH_THRESHOLD_PERCENT = 90

PILOT_REQUIRED_STEPS = {
    "org_settings",
    "users_roles",
    "integrations",
    "driver_protocol",
    "test_run",
}

LAUNCH_REQUIRED_STEPS = {
    "org_settings",
    "users_roles",
    "imports",
    "mappings",
    "integrations",
    "vehicle_qr",
    "driver_protocol",
    "test_run",
    "export_validation",
}


def derive_readiness_status(
    *, steps: list[ReadinessStep], percent_complete: int
) -> ReadinessStatus:
    """Determine readiness status from step progress and pilot/launch thresholds."""
    if any(step.status == "blocked" for step in steps):
        return "blocked"

    completed = {step.key for step in steps if step.status == "completed"}

    launch_requirements_met = LAUNCH_REQUIRED_STEPS.issubset(completed)
    if launch_requirements_met and percent_complete >= LAUNCH_THRESHOLD_PERCENT:
        return "launch_ready"

    pilot_requirements_met = PILOT_REQUIRED_STEPS.issubset(completed)
    if pilot_requirements_met and percent_complete >= PILOT_THRESHOLD_PERCENT:
        return "pilot_ready"

    if any(step.status in {"in_progress", "completed"} for step in steps):
        return "in_progress"

    return "not_started"
