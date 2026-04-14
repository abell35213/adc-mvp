import uuid

from app.onboarding.blockers import classify_blockers
from app.onboarding.progress import (
    OnboardingSignals,
    completion_percent,
    derive_step_statuses,
)
from app.onboarding.readiness import derive_readiness_status
from app.onboarding.service import build_onboarding_readiness


def test_classify_blockers_severity_buckets():
    blockers = classify_blockers(
        signals=OnboardingSignals(
            org_settings_configured=False,
            org_admin_count=0,
            successful_import_count=0,
            mapping_count=0,
            active_integration_count=0,
            protocol_configured=False,
            test_run_passed=False,
            export_validation_passed=False,
        )
    )

    by_code = {blocker.code: blocker for blocker in blockers}
    assert by_code["org_settings_incomplete"].severity == "critical"
    assert by_code["mappings_missing"].severity == "important"
    assert by_code["export_validation_failed"].severity == "critical"


def test_readiness_status_transitions_pilot_and_launch():
    pilot_steps = derive_step_statuses(
        signals=OnboardingSignals(
            org_settings_configured=True,
            org_admin_count=1,
            active_user_count=2,
            successful_import_count=1,
            mapping_count=0,
            active_integration_count=1,
            total_integration_count=1,
            protocol_configured=True,
            test_run_passed=True,
            export_validation_passed=False,
        ),
        blocked_step_keys=set(),
    )
    pilot_percent = completion_percent(pilot_steps)
    assert (
        derive_readiness_status(steps=pilot_steps, percent_complete=pilot_percent)
        == "pilot_ready"
    )

    launch_steps = derive_step_statuses(
        signals=OnboardingSignals(
            org_settings_configured=True,
            org_admin_count=1,
            active_user_count=2,
            successful_import_count=1,
            mapping_count=3,
            active_integration_count=1,
            total_integration_count=1,
            vehicles_total=2,
            qr_codes_generated=2,
            qr_codes_activated=2,
            protocol_configured=True,
            test_run_passed=True,
            export_validation_passed=True,
        ),
        blocked_step_keys=set(),
    )
    launch_percent = completion_percent(launch_steps)
    assert (
        derive_readiness_status(steps=launch_steps, percent_complete=launch_percent)
        == "launch_ready"
    )


def test_build_onboarding_readiness_uses_blocked_status_when_critical_exists():
    snapshot = build_onboarding_readiness(
        org_id=uuid.uuid4(),
        signals=OnboardingSignals(
            org_settings_configured=False,
            org_admin_count=0,
            active_user_count=1,
            successful_import_count=0,
            mapping_count=0,
            active_integration_count=0,
            total_integration_count=1,
            protocol_configured=False,
            test_run_passed=False,
            export_validation_passed=False,
        ),
    )

    assert snapshot.status == "blocked"
    blocked = {step.key for step in snapshot.steps if step.status == "blocked"}
    assert "org_settings" in blocked
    assert "integrations" in blocked
    assert len(snapshot.blockers) >= 1
