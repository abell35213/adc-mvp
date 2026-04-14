"""Onboarding readiness service for API routes and background jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.db.models import (
    DriverInstructionSet,
    DriverInstructionStep,
    DriverImportJob,
    DriverVehicleAssignment,
    Event,
    Export,
    ExternalMapping,
    IntegrationConnection,
    IntegrationOperation,
    Org,
    OrgOnboardingStepCompletion,
    User,
    UserOrg,
    VehicleQrToken,
)
from app.onboarding.blockers import blocked_step_keys, classify_blockers
from app.onboarding.models import (
    ImportJob,
    IntegrationValidationResult,
    OrgLaunchReadiness,
    TestIncidentRun,
    VehicleQrDeployment,
)
from app.onboarding.progress import (
    OnboardingSignals,
    completion_percent,
    derive_step_statuses,
)
from app.onboarding.readiness import derive_readiness_status
from app.security.permissions import Capability, has_capability


def _organization_basics_complete(org: Org) -> bool:
    contacts = org.contacts_json or []
    implementation_contact = org.implementation_contact_json or {}
    has_contact = any(
        bool((contact or {}).get("name")) and bool((contact or {}).get("email"))
        for contact in contacts
        if isinstance(contact, dict)
    )
    has_implementation_contact = bool(implementation_contact.get("name")) and bool(
        implementation_contact.get("email")
    )
    return all(
        [
            bool(org.legal_name),
            bool(org.display_name or org.name),
            bool(org.timezone),
            bool(org.region),
            has_contact,
            has_implementation_contact,
        ]
    )


def collect_onboarding_signals(db: Session, *, org_id: uuid.UUID) -> OnboardingSignals:
    """Collect normalized onboarding signals from persisted org state."""
    org = db.query(Org).filter(Org.id == org_id).first()
    if org is None:
        return OnboardingSignals()

    org_settings_configured = _organization_basics_complete(org)

    user_rows = (
        db.query(User)
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(UserOrg.org_id == org_id)
        .all()
    )
    active_users = [
        user for user in user_rows if bool(getattr(user, "is_active", True))
    ]
    org_admin_count = sum(1 for user in active_users if str(user.role) == "org_admin")
    safety_capable_user_count = sum(
        1
        for user in active_users
        if has_capability(user.role, Capability.INCIDENT_WRITE)
    )

    import_operations = (
        db.query(IntegrationOperation)
        .filter(
            IntegrationOperation.org_id == org_id,
            func.lower(IntegrationOperation.operation_type).like("%import%"),
        )
        .all()
    )
    successful_import_count = sum(
        1 for op in import_operations if op.status == "succeeded"
    )
    failed_import_count = sum(1 for op in import_operations if op.status == "failed")
    driver_import_jobs = (
        db.query(DriverImportJob).filter(DriverImportJob.org_id == org_id).all()
    )
    successful_driver_import_count = sum(
        1 for row in driver_import_jobs if row.status == "succeeded"
    )
    failed_driver_import_count = sum(
        1 for row in driver_import_jobs if row.status == "failed"
    )

    mapping_count = (
        db.query(ExternalMapping.mapping_id)
        .filter(ExternalMapping.org_id == org_id)
        .count()
    )

    integration_rows = (
        db.query(IntegrationConnection)
        .filter(IntegrationConnection.org_id == org_id)
        .all()
    )
    active_integration_count = sum(
        1 for row in integration_rows if row.status == "active"
    )

    vehicles_total = (
        db.query(func.count(distinct(DriverVehicleAssignment.adc_vehicle_id)))
        .filter(DriverVehicleAssignment.org_id == org_id)
        .scalar()
        or 0
    )
    qr_rows = db.query(VehicleQrToken).filter(VehicleQrToken.org_id == org_id).all()
    qr_codes_generated = len(qr_rows)
    qr_codes_activated = sum(1 for row in qr_rows if row.status == "active")
    qr_rotation_times = [
        row.created_at_utc for row in qr_rows if row.created_at_utc is not None
    ]

    instruction_set = (
        db.query(DriverInstructionSet)
        .filter(DriverInstructionSet.org_id == org_id)
        .order_by(DriverInstructionSet.created_at_utc.desc())
        .first()
    )
    enabled_step_count = 0
    if instruction_set is not None:
        enabled_step_count = (
            db.query(DriverInstructionStep.step_id)
            .filter(
                DriverInstructionStep.instruction_set_id
                == instruction_set.instruction_set_id,
                DriverInstructionStep.enabled.is_(True),
            )
            .count()
        )
    protocol_configured = bool(org.require_driver_ack and enabled_step_count > 0)

    test_run_event = (
        db.query(Event)
        .filter(
            Event.org_id == org_id,
            Event.event_type == "incident_protocol_initiated",
        )
        .order_by(Event.occurred_at_utc.desc())
        .first()
    )
    test_run_passed = test_run_event is not None

    latest_export = (
        db.query(Export)
        .filter(Export.org_id == org_id)
        .order_by(Export.updated_at_utc.desc(), Export.created_at_utc.desc())
        .first()
    )
    export_validation_passed = (
        latest_export is not None and latest_export.status == "ready"
    )

    has_started_activity = any(
        [
            len(active_users) > 0,
            len(import_operations) > 0,
            len(driver_import_jobs) > 0,
            mapping_count > 0,
            len(integration_rows) > 0,
            qr_codes_generated > 0,
            test_run_event is not None,
            latest_export is not None,
        ]
    )

    return OnboardingSignals(
        org_settings_configured=org_settings_configured,
        org_admin_count=org_admin_count,
        safety_capable_user_count=safety_capable_user_count,
        active_user_count=len(active_users),
        successful_import_count=successful_import_count,
        failed_import_count=failed_import_count,
        successful_driver_import_count=successful_driver_import_count,
        failed_driver_import_count=failed_driver_import_count,
        mapping_count=mapping_count,
        active_integration_count=active_integration_count,
        total_integration_count=len(integration_rows),
        vehicles_total=vehicles_total,
        qr_codes_generated=qr_codes_generated,
        qr_codes_activated=qr_codes_activated,
        last_qr_rotation_at_utc=max(qr_rotation_times) if qr_rotation_times else None,
        protocol_configured=protocol_configured,
        test_run_passed=test_run_passed,
        export_validation_passed=export_validation_passed,
        has_started_activity=has_started_activity,
    )


def build_onboarding_readiness(
    *,
    org_id: uuid.UUID,
    signals: OnboardingSignals,
    step_completion_overrides: dict[str, OrgOnboardingStepCompletion] | None = None,
) -> OrgLaunchReadiness:
    """Build a typed readiness snapshot from normalized onboarding signals."""
    classified = classify_blockers(signals=signals)
    steps = derive_step_statuses(
        signals=signals, blocked_step_keys=blocked_step_keys(classified)
    )
    for step in steps:
        completion = (step_completion_overrides or {}).get(step.key)
        if completion is None:
            continue
        if completion.is_completed:
            step.status = "completed"
            step.completed_at_utc = completion.completed_at_utc
            step.metadata = {
                "completed_by_user_id": str(completion.completed_by_user_id)
                if completion.completed_by_user_id
                else "",
                "completion_source": completion.completion_source or "unknown",
            }
        else:
            step.metadata = {
                "completion_source": completion.completion_source or "unknown"
            }
        step.updated_at_utc = completion.updated_at_utc
    percent_complete = completion_percent(steps)
    status = derive_readiness_status(steps=steps, percent_complete=percent_complete)

    import_jobs = [
        ImportJob(
            import_job_id="imports_success",
            provider="aggregated",
            status="succeeded" if signals.successful_import_count > 0 else "pending",
            records_total=signals.successful_import_count + signals.failed_import_count,
            records_succeeded=signals.successful_import_count,
            records_failed=signals.failed_import_count,
        ),
        ImportJob(
            import_job_id="drivers_imported",
            provider="driver_csv",
            status="succeeded"
            if signals.successful_driver_import_count > 0
            else "pending",
            records_total=signals.successful_driver_import_count
            + signals.failed_driver_import_count,
            records_succeeded=signals.successful_driver_import_count,
            records_failed=signals.failed_driver_import_count,
        ),
    ]

    integration_validations = [
        IntegrationValidationResult(
            integration_key="active_integrations",
            status="completed"
            if signals.active_integration_count > 0
            else "not_started",
            checked_at_utc=datetime.now(timezone.utc),
            detail=f"{signals.active_integration_count} active of {signals.total_integration_count} configured",
            severity="info" if signals.active_integration_count > 0 else "warning",
        )
    ]

    test_incident_run = TestIncidentRun(
        status="completed" if signals.test_run_passed else "not_started",
        findings=[]
        if signals.test_run_passed
        else ["No completed test incident protocol run detected."],
    )

    qr_deployment = VehicleQrDeployment(
        status="completed"
        if signals.vehicles_total > 0
        and signals.qr_codes_activated >= signals.vehicles_total
        else "in_progress"
        if signals.qr_codes_generated > 0
        else "not_started",
        vehicles_total=signals.vehicles_total,
        qr_codes_generated=signals.qr_codes_generated,
        qr_codes_activated=signals.qr_codes_activated,
        last_rotated_at_utc=signals.last_qr_rotation_at_utc,
    )

    return OrgLaunchReadiness(
        org_id=str(org_id),
        status=status,
        percent_complete=percent_complete,
        steps=steps,
        blockers=[item.to_model() for item in classified],
        import_jobs=import_jobs,
        integration_validations=integration_validations,
        vehicle_qr_deployment=qr_deployment,
        test_incident_run=test_incident_run,
        snapshot_created_at_utc=datetime.now(timezone.utc),
    )


def get_org_onboarding_readiness(
    db: Session, *, org_id: uuid.UUID
) -> OrgLaunchReadiness:
    """Reusable facade for API routes and background jobs."""
    signals = collect_onboarding_signals(db, org_id=org_id)
    overrides = list_step_completion_overrides(db, org_id=org_id)
    return build_onboarding_readiness(
        org_id=org_id, signals=signals, step_completion_overrides=overrides
    )


def list_step_completion_overrides(
    db: Session, *, org_id: uuid.UUID
) -> dict[str, OrgOnboardingStepCompletion]:
    rows = (
        db.query(OrgOnboardingStepCompletion)
        .filter(OrgOnboardingStepCompletion.org_id == org_id)
        .all()
    )
    return {row.step_key: row for row in rows}


def set_step_completion_override(
    db: Session,
    *,
    org_id: uuid.UUID,
    step_key: str,
    is_completed: bool,
    actor_user_id: uuid.UUID,
    source: str,
) -> OrgOnboardingStepCompletion:
    row = (
        db.query(OrgOnboardingStepCompletion)
        .filter(
            OrgOnboardingStepCompletion.org_id == org_id,
            OrgOnboardingStepCompletion.step_key == step_key,
        )
        .first()
    )
    if row is None:
        row = OrgOnboardingStepCompletion(org_id=org_id, step_key=step_key)
    row.is_completed = is_completed
    row.completed_by_user_id = actor_user_id if is_completed else None
    row.completed_at_utc = datetime.now(timezone.utc) if is_completed else None
    row.completion_source = source
    row.updated_at_utc = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
