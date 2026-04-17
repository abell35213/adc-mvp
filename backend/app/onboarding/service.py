"""Onboarding readiness service for API routes and background jobs."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    DriverInstructionSet,
    DriverInstructionStep,
    DriverImportJob,
    Event,
    Export,
    ExternalMapping,
    Driver,
    Incident,
    IntegrationConnection,
    IntegrationOperation,
    Org,
    OrgOnboardingStepCompletion,
    OrgExportValidationRun,
    OrgTestIncidentRun,
    OrgVehicleRegistry,
    User,
    UserOrg,
    VehicleQrToken,
)
from app.onboarding.blockers import blocked_step_keys, classify_blockers
from app.onboarding.models import (
    ImportJob,
    IntegrationValidationResult,
    OnboardingAlertCondition,
    OnboardingMetricsSnapshot,
    OrgLaunchReadiness,
    ExportValidationRun,
    ProtocolSetupStep,
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
from app.domain.packet_profiles import DEFAULT_PROFILE_BY_EXPORT_TYPE


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
        db.query(func.count(OrgVehicleRegistry.vehicle_id))
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    qr_rows = db.query(VehicleQrToken).filter(VehicleQrToken.org_id == org_id).all()
    qr_codes_generated = len(qr_rows)
    qr_rotation_times = [
        row.created_at_utc for row in qr_rows if row.created_at_utc is not None
    ]
    qr_codes_distributed = (
        db.query(func.count(OrgVehicleRegistry.vehicle_id))
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.is_active.is_(True),
            OrgVehicleRegistry.qr_deployment_status.in_(["distributed", "confirmed"]),
        )
        .scalar()
        or 0
    )
    qr_codes_confirmed = (
        db.query(func.count(OrgVehicleRegistry.vehicle_id))
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.is_active.is_(True),
            OrgVehicleRegistry.qr_deployment_status == "confirmed",
        )
        .scalar()
        or 0
    )

    active_scope = org.instruction_source or "default"
    instruction_set = (
        db.query(DriverInstructionSet)
        .filter(DriverInstructionSet.org_id == org_id)
        .filter(DriverInstructionSet.scope == active_scope)
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
    protocol_instruction_set_active = bool(
        instruction_set is not None and enabled_step_count > 0
    )
    safety_contact_configured = bool(org.safety_manager_phone)
    export_profiles_available = len(DEFAULT_PROFILE_BY_EXPORT_TYPE) > 0
    required_media_prompts_defaulted = protocol_instruction_set_active
    export_profile_defaulted = export_profiles_available
    protocol_configured = bool(
        protocol_instruction_set_active
        and safety_contact_configured
        and export_profiles_available
    )

    latest_test_run = (
        db.query(OrgTestIncidentRun)
        .filter(OrgTestIncidentRun.org_id == org_id)
        .order_by(OrgTestIncidentRun.started_at_utc.desc())
        .first()
    )
    test_run_event = (
        db.query(Event)
        .filter(
            Event.org_id == org_id,
            Event.event_type == "incident_protocol_initiated",
        )
        .order_by(Event.occurred_at_utc.desc())
        .first()
    )
    test_run_passed = bool(
        latest_test_run is not None and latest_test_run.status == "completed"
    )

    export_validation_rows = (
        db.query(OrgExportValidationRun)
        .filter(OrgExportValidationRun.org_id == org_id)
        .all()
    )
    successful_export_validation_count = sum(
        1 for row in export_validation_rows if row.status == "passed"
    )
    latest_export = (
        db.query(Export)
        .filter(Export.org_id == org_id)
        .order_by(Export.updated_at_utc.desc(), Export.created_at_utc.desc())
        .first()
    )
    export_validation_passed = successful_export_validation_count > 0
    total_export_validation_count = len(export_validation_rows)
    test_run_rows = db.query(OrgTestIncidentRun).filter(OrgTestIncidentRun.org_id == org_id).all()
    completed_test_run_count = sum(1 for row in test_run_rows if row.status == "completed")
    integration_validation_rows = (
        db.query(IntegrationValidationResult)
        .filter(IntegrationValidationResult.org_id == org_id)
        .all()
    )
    integration_validation_pass_count = sum(
        1
        for row in integration_validation_rows
        if row.credential_status == "completed"
        and row.capability_status == "completed"
        and row.mapping_status == "completed"
    )
    valid_driver_phone_count = (
        db.query(func.count(Driver.driver_id))
        .filter(
            Driver.org_id == org_id,
            Driver.is_active.is_(True),
            Driver.phone_e164.is_not(None),
            Driver.phone_e164.like("+%"),
            func.length(Driver.phone_e164) >= 11,
        )
        .scalar()
        or 0
    )
    total_driver_count = (
        db.query(func.count(Driver.driver_id))
        .filter(Driver.org_id == org_id, Driver.is_active.is_(True))
        .scalar()
        or 0
    )
    onboarding_activity_timestamps = [
        row.requested_at_utc
        for row in import_operations
        if row.requested_at_utc is not None
    ]
    onboarding_activity_timestamps.extend(
        [row.created_at_utc for row in driver_import_jobs if row.created_at_utc is not None]
    )
    onboarding_activity_timestamps.extend(
        [row.started_at_utc for row in test_run_rows if row.started_at_utc is not None]
    )
    onboarding_activity_timestamps.extend(
        [
            row.validated_at_utc
            for row in export_validation_rows
            if row.validated_at_utc is not None
        ]
    )
    now_utc = datetime.now(timezone.utc)
    integration_failure_window_start = now_utc.timestamp() - (24 * 3600)
    repeated_integration_failures = (
        db.query(IntegrationOperation.operation_id)
        .filter(
            IntegrationOperation.org_id == org_id,
            IntegrationOperation.status == "failed",
            IntegrationOperation.requested_at_utc
            >= datetime.fromtimestamp(integration_failure_window_start, tz=timezone.utc),
        )
        .count()
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
        qr_codes_distributed=qr_codes_distributed,
        qr_codes_confirmed=qr_codes_confirmed,
        last_qr_rotation_at_utc=max(qr_rotation_times) if qr_rotation_times else None,
        protocol_instruction_set_active=protocol_instruction_set_active,
        safety_contact_configured=safety_contact_configured,
        export_profiles_available=export_profiles_available,
        required_media_prompts_defaulted=required_media_prompts_defaulted,
        export_profile_defaulted=export_profile_defaulted,
        protocol_configured=protocol_configured,
        test_run_passed=test_run_passed,
        export_validation_passed=export_validation_passed,
        successful_export_validation_count=successful_export_validation_count,
        total_export_validation_count=total_export_validation_count,
        total_test_run_count=len(test_run_rows),
        completed_test_run_count=completed_test_run_count,
        integration_validation_pass_count=integration_validation_pass_count,
        integration_validation_total_count=len(integration_validation_rows),
        valid_driver_phone_count=valid_driver_phone_count,
        total_driver_count=total_driver_count,
        onboarding_started_at_utc=min(onboarding_activity_timestamps)
        if onboarding_activity_timestamps
        else None,
        latest_activity_at_utc=max(onboarding_activity_timestamps)
        if onboarding_activity_timestamps
        else None,
        repeated_integration_failures=repeated_integration_failures,
        has_started_activity=has_started_activity,
    )


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _build_onboarding_metrics(
    *, signals: OnboardingSignals, status: str, common_blockers: list[str]
) -> OnboardingMetricsSnapshot:
    now_utc = datetime.now(timezone.utc)
    started_at = signals.onboarding_started_at_utc
    elapsed_hours = (
        round((now_utc - started_at).total_seconds() / 3600, 2)
        if started_at is not None
        else None
    )
    pilot_or_better = status in {"pilot_ready", "launch_ready"}
    launch_ready = status == "launch_ready"
    return OnboardingMetricsSnapshot(
        onboarding_started_at_utc=started_at,
        latest_activity_at_utc=signals.latest_activity_at_utc,
        time_to_pilot_ready_hours=elapsed_hours if pilot_or_better else None,
        time_to_launch_ready_hours=elapsed_hours if launch_ready else None,
        import_success_rate=_safe_ratio(
            signals.successful_import_count,
            signals.successful_import_count + signals.failed_import_count,
        ),
        driver_import_success_rate=_safe_ratio(
            signals.successful_driver_import_count,
            signals.successful_driver_import_count + signals.failed_driver_import_count,
        ),
        qr_coverage_rate=_safe_ratio(signals.qr_codes_distributed, signals.vehicles_total),
        valid_driver_phone_ratio=_safe_ratio(
            signals.valid_driver_phone_count, signals.total_driver_count
        ),
        integration_validation_pass_rate=_safe_ratio(
            signals.integration_validation_pass_count,
            signals.integration_validation_total_count,
        ),
        sample_incident_completion_rate=_safe_ratio(
            signals.completed_test_run_count, signals.total_test_run_count
        ),
        export_validation_rate=_safe_ratio(
            signals.successful_export_validation_count,
            signals.total_export_validation_count,
        ),
        common_blockers=common_blockers,
    )


def _build_alert_conditions(
    *, signals: OnboardingSignals, status: str, critical_blocker_count: int
) -> list[OnboardingAlertCondition]:
    now_utc = datetime.now(timezone.utc)
    latest_activity = signals.latest_activity_at_utc
    stalled_onboarding = bool(
        signals.has_started_activity
        and latest_activity is not None
        and (now_utc - latest_activity).total_seconds() >= 7 * 24 * 3600
    )
    repeated_integration_failures = signals.repeated_integration_failures >= 3
    unresolved_critical_blockers = critical_blocker_count > 0
    low_qr_coverage = bool(
        signals.vehicles_total > 0 and _safe_ratio(signals.qr_codes_distributed, signals.vehicles_total) < 0.8
    )
    no_test_incident_near_launch = bool(
        status in {"pilot_ready", "launch_ready"}
        and (signals.completed_test_run_count == 0 or not signals.test_run_passed)
    )
    return [
        OnboardingAlertCondition(
            code="stalled_onboarding",
            title="Onboarding stalled",
            severity="warning",
            triggered=stalled_onboarding,
            detail="No onboarding activity detected in the last 7 days after onboarding started.",
        ),
        OnboardingAlertCondition(
            code="repeated_integration_failures",
            title="Repeated integration failures",
            severity="error",
            triggered=repeated_integration_failures,
            detail="Three or more integration operations have recently failed and require remediation.",
        ),
        OnboardingAlertCondition(
            code="unresolved_critical_blockers",
            title="Unresolved critical blockers",
            severity="error",
            triggered=unresolved_critical_blockers,
            detail="Critical blockers are still open and are preventing launch readiness.",
        ),
        OnboardingAlertCondition(
            code="low_pilot_qr_coverage",
            title="Low pilot QR coverage",
            severity="warning",
            triggered=low_qr_coverage,
            detail="Distributed QR coverage is below 80% of required active vehicles.",
        ),
        OnboardingAlertCondition(
            code="no_successful_test_incident_near_launch",
            title="No successful test incident near launch",
            severity="error",
            triggered=no_test_incident_near_launch,
            detail="No completed test incident run is available while readiness is targeting launch.",
        ),
    ]


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
        if step.key == "export_validation" and not signals.export_validation_passed:
            step.status = "not_started"
            step.completed_at_utc = None
            step.metadata = {
                "completion_source": "export_validation_run_required"
            }
    percent_complete = completion_percent(steps)
    status = derive_readiness_status(steps=steps, percent_complete=percent_complete)
    blocker_counts = Counter(item.code for item in classified)
    common_blockers = [code for code, _ in blocker_counts.most_common(5)]
    critical_blocker_count = sum(1 for item in classified if item.severity == "critical")

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
        and signals.qr_codes_distributed >= signals.vehicles_total
        else "in_progress"
        if signals.qr_codes_generated > 0
        else "not_started",
        vehicles_total=signals.vehicles_total,
        qr_codes_generated=signals.qr_codes_generated,
        qr_codes_distributed=signals.qr_codes_distributed,
        qr_codes_confirmed=signals.qr_codes_confirmed,
        last_rotated_at_utc=signals.last_qr_rotation_at_utc,
        coverage_blockers=[
            *(
                []
                if signals.qr_codes_generated >= signals.vehicles_total
                else ["required_vehicles_not_generated"]
            ),
            *(
                []
                if signals.qr_codes_distributed >= signals.vehicles_total
                else ["required_vehicles_not_distributed"]
            ),
        ],
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
        metrics=_build_onboarding_metrics(
            signals=signals, status=status, common_blockers=common_blockers
        ),
        alert_conditions=_build_alert_conditions(
            signals=signals,
            status=status,
            critical_blocker_count=critical_blocker_count,
        ),
        reporting_hooks={
            "internal_dashboard": {
                "metrics_path": "/org/onboarding/status#metrics",
                "alerts_path": "/org/onboarding/status#alert_conditions",
                "snapshot_created_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "reporting": {
                "org_id": str(org_id),
                "status": status,
                "percent_complete": percent_complete,
                "common_blockers": common_blockers,
            },
        },
        snapshot_created_at_utc=datetime.now(timezone.utc),
    )


def get_org_onboarding_readiness(
    db: Session, *, org_id: uuid.UUID
) -> OrgLaunchReadiness:
    """Reusable facade for API routes and background jobs."""
    signals = collect_onboarding_signals(db, org_id=org_id)
    overrides = list_step_completion_overrides(db, org_id=org_id)
    readiness = build_onboarding_readiness(
        org_id=org_id, signals=signals, step_completion_overrides=overrides
    )
    latest_test_run = get_latest_test_incident_run(db, org_id=org_id)
    if latest_test_run is not None:
        readiness.test_incident_run = _to_test_incident_run_model(latest_test_run)
    latest_export_validation = get_latest_export_validation_run(db, org_id=org_id)
    if latest_export_validation is not None:
        readiness.latest_export_validation = _to_export_validation_model(
            latest_export_validation
        )
    return readiness


def get_protocol_setup_step(
    db: Session, *, org_id: uuid.UUID
) -> ProtocolSetupStep:
    signals = collect_onboarding_signals(db, org_id=org_id)
    org = db.query(Org).filter(Org.id == org_id).first()
    if org is None:
        return ProtocolSetupStep(
            instruction_set_selected=False,
            instruction_source="default",
            safety_contact_configured=False,
            safety_manager_phone=None,
            required_media_prompts_defaulted=False,
            export_profile_defaulted=False,
            export_profiles_available=[],
        )
    return ProtocolSetupStep(
        instruction_set_selected=signals.protocol_instruction_set_active,
        instruction_source=org.instruction_source or "default",
        safety_contact_configured=signals.safety_contact_configured,
        safety_manager_phone=org.safety_manager_phone,
        required_media_prompts_defaulted=signals.required_media_prompts_defaulted,
        export_profile_defaulted=signals.export_profile_defaulted,
        export_profiles_available=sorted(DEFAULT_PROFILE_BY_EXPORT_TYPE.values()),
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


def _to_test_incident_run_model(row: OrgTestIncidentRun) -> TestIncidentRun:
    return TestIncidentRun(
        run_id=row.run_id,
        status=row.status,
        incident_id=str(row.incident_id) if row.incident_id is not None else None,
        started_at_utc=row.started_at_utc,
        completed_at_utc=row.completed_at_utc,
        step_results=list(row.step_results_json or []),
        findings=list(row.findings_json or []),
    )


def get_latest_test_incident_run(
    db: Session, *, org_id: uuid.UUID
) -> OrgTestIncidentRun | None:
    return (
        db.query(OrgTestIncidentRun)
        .filter(OrgTestIncidentRun.org_id == org_id)
        .order_by(OrgTestIncidentRun.started_at_utc.desc())
        .first()
    )


def create_export_validation_run(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    status: str,
    checks: dict[str, bool],
    details: dict[str, str],
    warnings: list[dict[str, str]],
    missing_items: list[dict[str, str]],
    incident_id: uuid.UUID | None = None,
    export_id: uuid.UUID | None = None,
) -> OrgExportValidationRun:
    row = OrgExportValidationRun(
        org_id=org_id,
        incident_id=incident_id,
        export_id=export_id,
        status="passed" if status == "completed" else "failed",
        results_json={"checks": checks, "details": details},
        warnings_json=warnings,
        missing_items_json=missing_items,
        validated_at_utc=datetime.now(timezone.utc),
        created_by_user_id=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_export_validation_run(
    db: Session, *, org_id: uuid.UUID
) -> OrgExportValidationRun | None:
    return (
        db.query(OrgExportValidationRun)
        .filter(OrgExportValidationRun.org_id == org_id)
        .order_by(OrgExportValidationRun.validated_at_utc.desc())
        .first()
    )


def _to_export_validation_model(row: OrgExportValidationRun) -> ExportValidationRun:
    results = row.results_json if isinstance(row.results_json, dict) else {}
    return ExportValidationRun(
        validation_run_id=row.validation_run_id,
        export_id=row.export_id,
        incident_id=str(row.incident_id) if row.incident_id is not None else None,
        status="completed" if row.status == "passed" else "blocked",
        validated_at_utc=row.validated_at_utc,
        checks=results.get("checks", {}) if isinstance(results.get("checks", {}), dict) else {},
        details=results.get("details", {}) if isinstance(results.get("details", {}), dict) else {},
        warnings=list(row.warnings_json or []),
        missing_items=list(row.missing_items_json or []),
    )


def list_test_incident_runs(
    db: Session, *, org_id: uuid.UUID
) -> list[OrgTestIncidentRun]:
    return (
        db.query(OrgTestIncidentRun)
        .filter(OrgTestIncidentRun.org_id == org_id)
        .order_by(OrgTestIncidentRun.started_at_utc.desc())
        .all()
    )


def create_test_incident_run(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    incident_id: uuid.UUID | None,
    findings: list[str] | None = None,
) -> TestIncidentRun:
    row = OrgTestIncidentRun(
        org_id=org_id,
        incident_id=incident_id,
        status="in_progress",
        findings_json=list(findings or []),
        step_results_json=[],
        created_by_user_id=actor_user_id,
        started_at_utc=datetime.now(timezone.utc),
    )
    db.add(row)
    if incident_id is not None:
        incident = (
            db.query(Incident)
            .filter(Incident.incident_id == incident_id, Incident.org_id == org_id)
            .first()
        )
        if incident is not None:
            incident.is_test_incident = True
            db.add(incident)
    db.commit()
    db.refresh(row)
    return _to_test_incident_run_model(row)


def get_test_incident_run_by_id(
    db: Session, *, org_id: uuid.UUID, run_id: uuid.UUID
) -> OrgTestIncidentRun | None:
    return (
        db.query(OrgTestIncidentRun)
        .filter(OrgTestIncidentRun.org_id == org_id, OrgTestIncidentRun.run_id == run_id)
        .first()
    )


def complete_test_incident_run_step(
    db: Session,
    *,
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    step_key: str,
    step_status: str,
    result: dict[str, object],
    source: str,
    actor_user_id: uuid.UUID,
) -> TestIncidentRun:
    row = get_test_incident_run_by_id(db, org_id=org_id, run_id=run_id)
    if row is None:
        raise ValueError("not_found")

    step_results = list(row.step_results_json or [])
    now_utc = datetime.now(timezone.utc)
    next_item = {
        "step_key": step_key,
        "status": step_status,
        "result": result,
        "source": source,
        "completed_by_user_id": str(actor_user_id),
        "completed_at_utc": now_utc.isoformat(),
    }
    replaced = False
    for index, existing in enumerate(step_results):
        if isinstance(existing, dict) and existing.get("step_key") == step_key:
            step_results[index] = next_item
            replaced = True
            break
    if not replaced:
        step_results.append(next_item)

    row.step_results_json = step_results
    row.status = "in_progress" if step_status in {"not_started", "in_progress"} else step_status
    if row.status == "completed":
        row.completed_at_utc = now_utc
        set_step_completion_override(
            db,
            org_id=org_id,
            step_key="testIncidentCompleted",
            is_completed=True,
            actor_user_id=actor_user_id,
            source=source,
        )
    elif row.status == "blocked":
        set_step_completion_override(
            db,
            org_id=org_id,
            step_key="testIncidentCompleted",
            is_completed=False,
            actor_user_id=actor_user_id,
            source=source,
        )
        row.completed_at_utc = None
    row.updated_at_utc = now_utc
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_test_incident_run_model(row)
