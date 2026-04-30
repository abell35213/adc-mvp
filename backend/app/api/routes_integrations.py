"""Integration and evidence diagnostics API routes."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.audit.emitter import emit_standard_audit_event
from app.api.schemas import (
    AuditSearchResponseItem,
    DriverImportJobCreateRequest,
    DriverImportJobCreateResponse,
    DriverImportJobResponse,
    EvidenceRequestSummary,
    EvidenceRetryActionRequest,
    EvidenceRetryActionResponse,
    EvidenceSummaryResponse,
    IntegrationConnectionHealthResponse,
    IntegrationConnectionUpsertRequest,
    IntegrationConnectionUpdateRequest,
    IntegrationConnectionValidateResponse,
    IntegrationValidationResultResponse,
    IntegrationOperationDiagnosticsResponse,
    OrgLaunchReadinessResponse,
    OrgInviteUserRequest,
    OrgInviteUserResponse,
    OrgMappingsAssignmentConfidence,
    OrgMappingsIssue,
    OrgMappingsIssuesResponse,
    OrgMappingsPilotReadinessFlags,
    OrgMappingsStaleWarnings,
    OrgMappingsSummaryCounts,
    OrgMappingsSummaryResponse,
    OrgOnboardingStepUpdateRequest,
    ProtocolSetupStepResponse,
    OrgSettingsResponse,
    OrgSettingsUpdateRequest,
    OrgPatchUserRoleRequest,
    TestIncidentRunCreateRequest,
    TestIncidentRunResponse,
    TestIncidentRunsResponse,
    TestIncidentRunStepCompleteRequest,
    OrgUserInviteSummary,
    OrgUserSummary,
    OrgUsersResponse,
    VehicleImportJobCreateRequest,
    VehicleImportJobCreateResponse,
    VehicleImportJobResponse,
    VehicleQrBulkGenerateRequest,
    VehicleQrBulkGenerateResponse,
    VehicleQrGenerateResponse,
    VehicleQrStatsResponse,
)
from app.core.config import settings
from app.core.deps import get_current_user, require_user_role
from app.core.logging import get_request_id
from app.db.models import (
    EvidenceRequest,
    IntegrationConnection,
    IntegrationOperation,
    IntegrationValidationResult,
    OrgUserInvite,
    Org,
    User,
    UserOrg,
    DriverImportJob,
    Driver,
    DriverVehicleAssignment,
    ExternalMapping,
    AuditEvent,
    OrgVehicleRegistry,
    VehicleImportJob,
    VehicleQrToken,
    Event,
    Export,
    Incident,
)
from app.db.session import get_db
from app.integrations.webhooks.handlers import (
    persist_twilio_voice_callback,
    process_twilio_status_callback,
)
from app.integrations.webhooks.signatures import (
    parse_form_encoded_body,
    validate_twilio_signature,
)
from app.security.authn import build_user_auth_context
from app.observability.redaction import redact_payload_for_storage
from app.services.dashcam_capture_service import queue_dashcam_capture
from app.services.telematics_capture_service import queue_telematics_capture
from app.services.phone_normalize import normalize_phone
from app.services.vehicle_import_service import (
    create_vehicle_import_job,
    run_vehicle_import_job,
)
from app.services.driver_import_service import (
    create_driver_import_job,
    run_driver_import_job,
)
from app.onboarding.progress import STEP_DEFINITIONS
from app.onboarding.service import (
    complete_test_incident_run_step,
    collect_onboarding_signals,
    create_export_validation_run,
    create_test_incident_run,
    get_org_onboarding_readiness,
    get_protocol_setup_step,
    get_test_incident_run_by_id,
    list_test_incident_runs,
    set_step_completion_override,
)
from app.security.permissions import (
    CANONICAL_ROLES,
    Capability,
    Role,
    has_capability,
    normalize_role,
)
from app.domain.system_event_types import SystemEventType
from app.services.pdf_render import render_pdf
from app.services.qr_image import qr_png_data_uri
from app.services.export_builder import build_export_package
from app.services.vault_fs import VaultFilesystem

router = APIRouter()

_integration_admin = require_user_role("system_admin", "org_admin", "support_admin")
_org_user_admin = require_user_role("system_admin", "org_admin", "support_admin")
_PILOT_MIN_MAPPED_DRIVERS = 3
_PILOT_MIN_MAPPED_VEHICLES = 3
_ASSIGNMENT_CONFIDENCE_MEDIUM_THRESHOLD = 0.7
_ASSIGNMENT_CONFIDENCE_HIGH_THRESHOLD = 0.9
_PILOT_REQUIRED_DOMAINS = {"telematics", "messaging"}


def _first_org_id(context) -> uuid.UUID:
    return context.org_ids[0]


def _require_phase6_capability(current_user: User, capability: Capability, *, message: str) -> None:
    if has_capability(current_user.role, capability):
        return
    raise HTTPException(status_code=403, detail=message)


def _emit_org_audit(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    outcome: str = "success",
    metadata: dict | None = None,
    event_type: str | None = None,
) -> None:
    emit_standard_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(actor.id),
        action=action,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        outcome=outcome,
        metadata=metadata or {},
    )


def _to_readiness_response(readiness) -> OrgLaunchReadinessResponse:
    return OrgLaunchReadinessResponse.model_validate(
        {
            "org_id": readiness.org_id,
            "status": readiness.status,
            "percent_complete": readiness.percent_complete,
            "steps": [asdict(item) for item in readiness.steps],
            "blockers": [asdict(item) for item in readiness.blockers],
            "import_jobs": [asdict(item) for item in readiness.import_jobs],
            "integration_validations": [
                asdict(item) for item in readiness.integration_validations
            ],
            "vehicle_qr_deployment": asdict(readiness.vehicle_qr_deployment)
            if readiness.vehicle_qr_deployment is not None
            else None,
            "test_incident_run": asdict(readiness.test_incident_run)
            if readiness.test_incident_run is not None
            else None,
            "latest_export_validation": asdict(readiness.latest_export_validation)
            if readiness.latest_export_validation is not None
            else None,
            "snapshot_created_at_utc": readiness.snapshot_created_at_utc,
        }
    )


def _to_test_run_response_row(row) -> TestIncidentRunResponse:
    return TestIncidentRunResponse(
        run_id=row.run_id,
        status=row.status,
        incident_id=row.incident_id,
        started_at_utc=row.started_at_utc,
        completed_at_utc=row.completed_at_utc,
        step_results=list(row.step_results_json or []),
        findings=list(row.findings_json or []),
    )


def _role_counts_for_org(db: Session, *, org_id: uuid.UUID) -> dict[str, int]:
    rows = (
        db.query(User.role)
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(UserOrg.org_id == org_id, User.is_active.is_(True))
        .all()
    )
    counts = {role: 0 for role in CANONICAL_ROLES}
    for (role,) in rows:
        normalized = normalize_role(role).value
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _role_violations(*, role_counts: dict[str, int]) -> list[str]:
    violations: list[str] = []
    if role_counts.get("org_admin", 0) < 1:
        violations.append("no org admin assigned")
    safety_capable_count = sum(
        count
        for role, count in role_counts.items()
        if has_capability(role, Capability.INCIDENT_WRITE)
    )
    if safety_capable_count < 1:
        violations.append("no safety manager assigned")
    return violations


def _build_org_mapping_summary(
    db: Session, *, org_id: uuid.UUID
) -> OrgMappingsSummaryResponse:
    active_drivers = (
        db.query(Driver)
        .filter(Driver.org_id == org_id, Driver.is_active.is_(True))
        .all()
    )
    active_vehicles = (
        db.query(OrgVehicleRegistry)
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.is_active.is_(True),
        )
        .all()
    )
    active_driver_ids = {str(row.driver_id).lower() for row in active_drivers}
    active_vehicle_unit_numbers = {row.unit_number.lower() for row in active_vehicles}

    mapped_driver_ids = {
        row.internal_entity_id.lower()
        for row in db.query(ExternalMapping)
        .filter(
            ExternalMapping.org_id == org_id,
            ExternalMapping.internal_entity_type == "driver",
            ExternalMapping.status == "active",
        )
        .all()
    }
    mapped_vehicle_unit_numbers = {
        row.internal_entity_id.lower()
        for row in db.query(ExternalMapping)
        .filter(
            ExternalMapping.org_id == org_id,
            ExternalMapping.internal_entity_type == "vehicle",
            ExternalMapping.status == "active",
        )
        .all()
    }

    mapped_drivers = len(active_driver_ids.intersection(mapped_driver_ids))
    mapped_vehicles = len(
        active_vehicle_unit_numbers.intersection(mapped_vehicle_unit_numbers)
    )

    assigned_driver_ids = {
        str(row.driver_id).lower()
        for row in db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.org_id == org_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        )
        .all()
    }
    assigned_mapped_drivers = len(
        assigned_driver_ids.intersection(active_driver_ids.intersection(mapped_driver_ids))
    )
    assignment_score = (
        assigned_mapped_drivers / mapped_drivers if mapped_drivers > 0 else 0.0
    )
    if assignment_score >= _ASSIGNMENT_CONFIDENCE_HIGH_THRESHOLD:
        assignment_level = "high"
    elif assignment_score >= _ASSIGNMENT_CONFIDENCE_MEDIUM_THRESHOLD:
        assignment_level = "medium"
    else:
        assignment_level = "low"

    blocking_credential_count = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.org_id == org_id,
            IntegrationConnection.status.in_(["inactive", "error"]),
            IntegrationConnection.credentials_ref.is_(None),
        )
        .count()
    )
    no_blocking_integration_credentials = blocking_credential_count == 0
    enough_mapped_drivers_for_pilot = mapped_drivers >= _PILOT_MIN_MAPPED_DRIVERS
    enough_mapped_vehicles_for_pilot = mapped_vehicles >= _PILOT_MIN_MAPPED_VEHICLES
    qr_stats = _vehicle_qr_stats(db, org_id=org_id)
    enough_qr_generated = qr_stats.generated_count >= qr_stats.required_vehicle_count
    enough_qr_distributed = (
        qr_stats.distributed_count >= qr_stats.required_vehicle_count
    )

    return OrgMappingsSummaryResponse(
        drivers=OrgMappingsSummaryCounts(
            total=len(active_driver_ids),
            mapped=mapped_drivers,
            unmapped=max(0, len(active_driver_ids) - mapped_drivers),
        ),
        vehicles=OrgMappingsSummaryCounts(
            total=len(active_vehicle_unit_numbers),
            mapped=mapped_vehicles,
            unmapped=max(0, len(active_vehicle_unit_numbers) - mapped_vehicles),
        ),
        assignment_confidence=OrgMappingsAssignmentConfidence(
            level=assignment_level,
            score=round(assignment_score, 4),
            assigned_mapped_drivers=assigned_mapped_drivers,
            mapped_drivers=mapped_drivers,
        ),
        stale_warnings=OrgMappingsStaleWarnings(
            placeholder_supported=True,
            stale_count=0,
            stale_warning_codes=[],
        ),
        pilot_readiness=OrgMappingsPilotReadinessFlags(
            enough_mapped_drivers_for_pilot=enough_mapped_drivers_for_pilot,
            enough_mapped_vehicles_for_pilot=enough_mapped_vehicles_for_pilot,
            enough_qr_generated_for_required_vehicles=enough_qr_generated,
            enough_qr_distributed_for_required_vehicles=enough_qr_distributed,
            no_blocking_integration_credentials=no_blocking_integration_credentials,
            pilot_scope_ready=(
                enough_mapped_drivers_for_pilot
                and enough_mapped_vehicles_for_pilot
                and enough_qr_generated
                and enough_qr_distributed
                and no_blocking_integration_credentials
            ),
        ),
    )


def _build_org_mapping_issues(
    summary: OrgMappingsSummaryResponse,
) -> OrgMappingsIssuesResponse:
    issues: list[OrgMappingsIssue] = []

    if summary.drivers.unmapped > 0:
        issues.append(
            OrgMappingsIssue(
                code="MAPPED_DRIVERS_REQUIRED",
                message=(
                    f"{summary.drivers.unmapped} active driver(s) are not mapped to a provider reference."
                ),
                severity="error",
                blocker_panel_action="open_driver_mappings",
            )
        )

    if summary.vehicles.unmapped > 0:
        issues.append(
            OrgMappingsIssue(
                code="MAPPED_VEHICLES_REQUIRED",
                message=(
                    f"{summary.vehicles.unmapped} active vehicle(s) are not mapped to a provider reference."
                ),
                severity="error",
                blocker_panel_action="open_vehicle_mappings",
            )
        )

    if summary.assignment_confidence.level == "low":
        issues.append(
            OrgMappingsIssue(
                code="ASSIGNMENT_CONFIDENCE_LOW",
                message=(
                    "Driver-to-vehicle assignment confidence is low for currently mapped drivers."
                ),
                severity="warning",
                blocker_panel_action="review_driver_assignments",
            )
        )

    if not summary.pilot_readiness.no_blocking_integration_credentials:
        issues.append(
            OrgMappingsIssue(
                code="BLOCKING_INTEGRATION_CREDENTIALS",
                message=(
                    "One or more integration connections are missing required credentials."
                ),
                severity="error",
                blocker_panel_action="fix_integration_credentials",
            )
        )

    if not summary.pilot_readiness.enough_qr_generated_for_required_vehicles:
        issues.append(
            OrgMappingsIssue(
                code="VEHICLE_QR_GENERATION_REQUIRED",
                message="Required pilot vehicles are missing generated QR codes.",
                severity="error",
                blocker_panel_action="generate_vehicle_qr",
            )
        )

    if not summary.pilot_readiness.enough_qr_distributed_for_required_vehicles:
        issues.append(
            OrgMappingsIssue(
                code="VEHICLE_QR_DISTRIBUTION_REQUIRED",
                message="Required pilot vehicles have QR codes that are not yet distributed.",
                severity="error",
                blocker_panel_action="distribute_vehicle_qr",
            )
        )

    if summary.stale_warnings.stale_count > 0:
        issues.append(
            OrgMappingsIssue(
                code="STALE_MAPPING_WARNINGS",
                message="Stale mapping warnings were detected and require review.",
                severity="warning",
                blocker_panel_action="review_stale_mapping_warnings",
            )
        )

    return OrgMappingsIssuesResponse(issues=issues)


def _evaluate_integration_validation(
    *,
    db: Session,
    org_id: uuid.UUID,
    row: IntegrationConnection,
) -> tuple[str, str, str, list[str], bool, str]:
    messages: list[str] = []

    credential_status = "pass"
    if not row.credentials_ref:
        credential_status = "fail"
        messages.append(
            f"Add credentials for {row.provider}/{row.domain} to enable validation."
        )
    elif row.status == "inactive":
        credential_status = "fail"
        messages.append(
            f"Enable {row.provider}/{row.domain}; inactive integrations cannot pass validation."
        )

    org_connections = (
        db.query(IntegrationConnection).filter(IntegrationConnection.org_id == org_id).all()
    )
    active_domains = {
        str(connection.domain).lower()
        for connection in org_connections
        if connection.status == "active" and connection.domain
    }
    missing_required_domains = sorted(_PILOT_REQUIRED_DOMAINS - active_domains)
    if not missing_required_domains:
        capability_status = "pass"
    elif row.domain and str(row.domain).lower() in _PILOT_REQUIRED_DOMAINS:
        capability_status = "partial_support"
        messages.append(
            "Pilot readiness requires both telematics and messaging providers; "
            f"still missing: {', '.join(missing_required_domains)}."
        )
    else:
        capability_status = "fail"
        messages.append(
            "Selected provider does not satisfy pilot-required capabilities. "
            "Configure active telematics and messaging integrations."
        )

    mapping_summary = _build_org_mapping_summary(db, org_id=org_id)
    if (
        mapping_summary.pilot_readiness.enough_mapped_drivers_for_pilot
        and mapping_summary.pilot_readiness.enough_mapped_vehicles_for_pilot
    ):
        mapping_status = "pass"
    elif mapping_summary.drivers.mapped > 0 or mapping_summary.vehicles.mapped > 0:
        mapping_status = "partial_support"
        messages.append(
            "Mapping is partially complete. Map at least "
            f"{_PILOT_MIN_MAPPED_DRIVERS} drivers and {_PILOT_MIN_MAPPED_VEHICLES} vehicles."
        )
    else:
        mapping_status = "fail"
        messages.append(
            "No provider mappings found. Map drivers and vehicles before pilot launch."
        )

    valid = all(
        status == "pass"
        for status in (credential_status, capability_status, mapping_status)
    )
    message = "Connection validated" if valid else "Validation failed with actionable blockers"
    return credential_status, capability_status, mapping_status, messages, valid, message


def _run_vehicle_import_background(
    db: Session,
    *,
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    csv_content: str,
    header_mapping: dict[str, str],
    inactive_unit_numbers: list[str],
) -> None:
    run_vehicle_import_job(
        db,
        job_id=job_id,
        org_id=org_id,
        csv_content=csv_content,
        header_mapping=header_mapping,
        inactive_unit_numbers={
            item.strip().lower() for item in inactive_unit_numbers if item.strip()
        },
    )
    completed = db.query(VehicleImportJob).filter(VehicleImportJob.job_id == job_id).first()
    emit_standard_audit_event(
        db,
        org_id=org_id,
        actor_type="system",
        actor_id="vehicle_import_worker",
        action="onboarding.vehicle_import.apply",
        event_type="onboarding_vehicle_import_applied",
        entity_type="vehicle_import_job",
        entity_id=str(job_id),
        outcome="success" if completed and completed.status == "completed" else "failure",
        metadata={
            "job_status": completed.status if completed else None,
            "records_processed": completed.records_processed if completed else None,
            "records_imported": completed.records_imported if completed else None,
            "records_updated": completed.records_updated if completed else None,
            "records_errored": completed.records_errored if completed else None,
        },
    )


def _get_required_vehicle(
    db: Session, *, org_id: uuid.UUID, vehicle_id: str
) -> OrgVehicleRegistry:
    vehicle = (
        db.query(OrgVehicleRegistry)
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.unit_number == vehicle_id,
            OrgVehicleRegistry.is_active.is_(True),
        )
        .first()
    )
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


def _emit_vehicle_qr_event(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    vehicle_id: str,
    payload: dict,
) -> None:
    db.add(
        Event(
            org_id=org_id,
            incident_id=None,
            event_type=action,
            actor_type="admin",
            actor_id=str(actor_id),
            payload={"adc_vehicle_id": vehicle_id, **payload},
        )
    )


def _vehicle_qr_stats(db: Session, *, org_id: uuid.UUID) -> VehicleQrStatsResponse:
    required_rows = (
        db.query(OrgVehicleRegistry)
        .filter(
            OrgVehicleRegistry.org_id == org_id,
            OrgVehicleRegistry.is_active.is_(True),
        )
        .all()
    )
    required_ids = {row.unit_number for row in required_rows}
    generated_ids = {
        row.adc_vehicle_id
        for row in db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.status == "active",
        )
        .all()
    }
    distributed_count = sum(
        1
        for row in required_rows
        if row.qr_deployment_status in {"distributed", "confirmed"}
    )
    confirmed_count = sum(
        1 for row in required_rows if row.qr_deployment_status == "confirmed"
    )
    blockers: list[str] = []
    if len(required_ids - generated_ids) > 0:
        blockers.append("required_vehicles_not_generated")
    if distributed_count < len(required_rows):
        blockers.append("required_vehicles_not_distributed")
    return VehicleQrStatsResponse(
        required_vehicle_count=len(required_rows),
        generated_count=len(required_ids.intersection(generated_ids)),
        distributed_count=distributed_count,
        confirmed_count=confirmed_count,
        coverage_blockers=blockers,
    )


def _to_vehicle_import_job_response(job: VehicleImportJob) -> VehicleImportJobResponse:
    return VehicleImportJobResponse(
        job_id=job.job_id,
        provider=job.provider,
        status=job.status,
        started_at_utc=job.started_at_utc,
        completed_at_utc=job.completed_at_utc,
        records_total=job.records_total,
        records_processed=job.records_processed,
        records_imported=job.records_imported,
        records_updated=job.records_updated,
        records_skipped=job.records_skipped,
        records_errored=job.records_errored,
        warnings=job.warnings_json or [],
        outcomes=job.outcomes_json or {},
        summary=job.summary_json or {},
        error_message=job.error_message,
    )


def _run_driver_import_background(
    db: Session,
    *,
    job_id: uuid.UUID,
    org_id: uuid.UUID,
    csv_content: str,
    header_mapping: dict[str, str],
    inactive_mobile_phones: list[str],
) -> None:
    inactive_phones: set[str] = set()
    for raw in inactive_mobile_phones:
        if not raw or not raw.strip():
            continue
        try:
            inactive_phones.add(normalize_phone(raw))
        except ValueError:
            continue
    run_driver_import_job(
        db,
        job_id=job_id,
        org_id=org_id,
        csv_content=csv_content,
        header_mapping=header_mapping,
        inactive_phones=inactive_phones,
    )
    completed = db.query(DriverImportJob).filter(DriverImportJob.job_id == job_id).first()
    emit_standard_audit_event(
        db,
        org_id=org_id,
        actor_type="system",
        actor_id="driver_import_worker",
        action="onboarding.driver_import.apply",
        event_type="onboarding_driver_import_applied",
        entity_type="driver_import_job",
        entity_id=str(job_id),
        outcome="success" if completed and completed.status == "completed" else "failure",
        metadata={
            "job_status": completed.status if completed else None,
            "records_processed": completed.records_processed if completed else None,
            "records_imported": completed.records_imported if completed else None,
            "records_updated": completed.records_updated if completed else None,
            "records_errored": completed.records_errored if completed else None,
        },
    )


def _to_driver_import_job_response(job: DriverImportJob) -> DriverImportJobResponse:
    return DriverImportJobResponse(
        job_id=job.job_id,
        provider=job.provider,
        status=job.status,
        started_at_utc=job.started_at_utc,
        completed_at_utc=job.completed_at_utc,
        records_total=job.records_total,
        records_processed=job.records_processed,
        records_imported=job.records_imported,
        records_updated=job.records_updated,
        records_skipped=job.records_skipped,
        records_errored=job.records_errored,
        warnings=job.warnings_json or [],
        outcomes=job.outcomes_json or {},
        summary=job.summary_json or {},
        error_message=job.error_message,
    )


@router.get("/org/settings", response_model=OrgSettingsResponse)
def get_org_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.ORG_SETTINGS_READ, message="Insufficient permission to view org settings"
    )
    context = build_user_auth_context(db, current_user)
    org = db.query(Org).filter(Org.id == _first_org_id(context)).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgSettingsResponse(
        legal_name=org.legal_name,
        display_name=org.display_name or org.name,
        timezone=org.timezone,
        region=org.region,
        contacts=org.contacts_json or [],
        implementation_contact=org.implementation_contact_json or None,
        logo_url=org.logo_url,
    )


@router.patch("/org/settings", response_model=OrgSettingsResponse)
def patch_org_settings(
    payload: OrgSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.ORG_SETTINGS_WRITE, message="Insufficient permission to manage org settings"
    )
    context = build_user_auth_context(db, current_user)
    org = db.query(Org).filter(Org.id == _first_org_id(context)).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    updates = payload.model_dump(exclude_unset=True)
    for field in ("legal_name", "display_name", "timezone", "region", "logo_url"):
        if field in updates:
            setattr(org, field, updates[field])
    if "display_name" in updates and updates["display_name"]:
        org.name = updates["display_name"]
    if "contacts" in updates:
        org.contacts_json = [item for item in updates["contacts"] or []]
    if "implementation_contact" in updates:
        org.implementation_contact_json = updates["implementation_contact"] or {}
    _emit_org_audit(
        db,
        org_id=org.id,
        actor=current_user,
        action="org.settings.update",
        event_type="org_settings_updated",
        entity_type="org_settings",
        entity_id=str(org.id),
        metadata={"updated_fields": sorted(updates.keys())},
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    return OrgSettingsResponse(
        legal_name=org.legal_name,
        display_name=org.display_name or org.name,
        timezone=org.timezone,
        region=org.region,
        contacts=org.contacts_json or [],
        implementation_contact=org.implementation_contact_json or None,
        logo_url=org.logo_url,
    )


@router.get("/org/onboarding/status", response_model=OrgLaunchReadinessResponse)
def get_org_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.READINESS_VIEW, message="Insufficient permission to view onboarding readiness"
    )
    context = build_user_auth_context(db, current_user)
    readiness = get_org_onboarding_readiness(db, org_id=_first_org_id(context))
    return _to_readiness_response(readiness)


@router.post("/org/test-runs", response_model=TestIncidentRunResponse, status_code=201)
def create_org_test_run(
    payload: TestIncidentRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.TEST_RUNS_WRITE, message="Insufficient permission to manage sample tests"
    )
    context = build_user_auth_context(db, current_user)
    run = create_test_incident_run(
        db,
        org_id=_first_org_id(context),
        actor_user_id=current_user.id,
        incident_id=payload.incident_id,
        findings=payload.findings,
    )
    _emit_org_audit(
        db,
        org_id=_first_org_id(context),
        actor=current_user,
        action="onboarding.test_run.create",
        event_type="onboarding_test_run_created",
        entity_type="test_run",
        entity_id=str(run.run_id),
        metadata={"incident_id": str(payload.incident_id) if payload.incident_id else None},
    )
    return TestIncidentRunResponse.model_validate(asdict(run))


@router.get("/org/test-runs", response_model=TestIncidentRunsResponse)
def list_org_test_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.TEST_RUNS_READ, message="Insufficient permission to access sample tests"
    )
    context = build_user_auth_context(db, current_user)
    rows = list_test_incident_runs(db, org_id=_first_org_id(context))
    return TestIncidentRunsResponse(runs=[_to_test_run_response_row(row) for row in rows])


@router.get("/org/test-runs/{run_id}", response_model=TestIncidentRunResponse)
def get_org_test_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.TEST_RUNS_READ, message="Insufficient permission to access sample tests"
    )
    context = build_user_auth_context(db, current_user)
    row = get_test_incident_run_by_id(db, org_id=_first_org_id(context), run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    return _to_test_run_response_row(row)


@router.post(
    "/org/test-runs/{run_id}/complete-step",
    response_model=TestIncidentRunResponse,
)
def complete_org_test_run_step(
    run_id: uuid.UUID,
    payload: TestIncidentRunStepCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.TEST_RUNS_WRITE, message="Insufficient permission to manage sample tests"
    )
    context = build_user_auth_context(db, current_user)
    try:
        run = complete_test_incident_run_step(
            db,
            org_id=_first_org_id(context),
            run_id=run_id,
            step_key=payload.step_key,
            step_status=payload.status,
            result=payload.result,
            source=payload.source,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "not_found":
            raise HTTPException(status_code=404, detail="Test run not found") from exc
        raise
    _emit_org_audit(
        db,
        org_id=_first_org_id(context),
        actor=current_user,
        action="onboarding.test_run.complete_step",
        event_type="onboarding_test_run_step_completed",
        entity_type="test_run",
        entity_id=str(run_id),
        metadata={"step_key": payload.step_key, "step_status": payload.status},
    )
    return TestIncidentRunResponse.model_validate(asdict(run))


@router.post("/org/onboarding/export-check", response_model=OrgLaunchReadinessResponse)
def run_org_onboarding_export_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.ONBOARDING_WRITE, message="Insufficient permission to run onboarding validations"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    org = db.query(Org).filter(Org.id == org_id).first()
    latest_incident = (
        db.query(Incident)
        .filter(Incident.org_id == org_id)
        .order_by(Incident.created_at_utc.desc())
        .first()
    )
    if latest_incident is None:
        latest_incident = Incident(org_id=org_id, status="open", is_test_incident=True)
        db.add(latest_incident)
        db.commit()
        db.refresh(latest_incident)

    branding = {
        "display_name": (org.display_name or org.name) if org else "",
        "logo_url": org.logo_url if org and org.logo_url else "",
    }
    options = {"profile_id": "court_defense_v1", "branding": branding}
    build_result = build_export_package(
        incident_id=str(latest_incident.incident_id),
        export_id=str(uuid.uuid4()),
        artifacts=[],
        events=[],
        s3=type("_NoopS3", (), {"download": lambda self, _key: b""})(),
        options=options,
        incident=latest_incident,
        export=None,
    )
    vault_root = settings.VAULT_ROOT
    if settings.APP_ENV == "test":
        vault_root = str(Path(tempfile.gettempdir()) / "adc_mvp_vault")
    try:
        Path(vault_root).mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        vault_root = str(Path(tempfile.gettempdir()) / "adc_mvp_vault")
        Path(vault_root).mkdir(parents=True, exist_ok=True)
    vault = VaultFilesystem(vault_root)
    zip_key = f"onboarding/sample_exports/{org_id}/{uuid.uuid4()}.zip"
    vault.put_bytes(zip_key, build_result.zip_bytes)
    downloaded_bytes = vault.get_bytes(zip_key)

    export_row = Export(
        org_id=org_id,
        incident_id=latest_incident.incident_id,
        export_type="court_defense",
        profile_id="court_defense_v1",
        status="ready",
        progress_stage="ready_for_download",
        options_json={
            "branding": branding,
            "file_manifest": build_result.file_manifest,
            "warnings": build_result.warnings,
            "missing_items": build_result.missing_items,
        },
        s3_bucket="vault_fs",
        s3_key=zip_key,
        byte_size=build_result.byte_size,
        package_sha256=build_result.package_sha256,
    )
    db.add(export_row)
    db.commit()
    db.refresh(export_row)

    required_files = {
        "01_Incident_Summary.json",
        "02_Evidence_Inventory.csv",
        "03_Chain_of_Custody.csv",
        "04_Timeline.csv",
        "05_Driver_Statement.txt",
        "00_Cover_Summary.pdf",
    }
    included_file_names = {path.rsplit("/", 1)[-1] for path in build_result.included_files}
    checks = {
        "required_sections_present": required_files.issubset(included_file_names),
        "branding_correct": branding
        == ((export_row.options_json or {}).get("branding") if isinstance(export_row.options_json, dict) else {}),
        "warnings_behavior_ok": isinstance(build_result.warnings, list)
        and isinstance(build_result.missing_items, list),
        "file_download_success": bool(downloaded_bytes) and downloaded_bytes == build_result.zip_bytes,
    }
    details = {
        "required_sections_found": str(sorted(included_file_names.intersection(required_files))),
        "warnings_count": str(len(build_result.warnings)),
        "missing_items_count": str(len(build_result.missing_items)),
        "download_key": zip_key,
    }
    status = "completed" if all(checks.values()) else "blocked"
    create_export_validation_run(
        db,
        org_id=org_id,
        actor_user_id=current_user.id,
        status=status,
        checks=checks,
        details=details,
        warnings=build_result.warnings,
        missing_items=build_result.missing_items,
        incident_id=latest_incident.incident_id,
        export_id=export_row.export_id,
    )
    set_step_completion_override(
        db,
        org_id=org_id,
        step_key="export_validation",
        is_completed=status == "completed",
        actor_user_id=current_user.id,
        source="export_check_action",
    )
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.export_validation.run",
        event_type="onboarding_export_validation_run",
        entity_type="export_validation",
        entity_id=str(export_row.export_id),
        metadata={
            "status": status,
            "checks": checks,
            "incident_id": str(latest_incident.incident_id),
        },
    )
    refreshed = get_org_onboarding_readiness(db, org_id=org_id)
    return _to_readiness_response(refreshed)


@router.get(
    "/org/onboarding/protocol-setup-step",
    response_model=ProtocolSetupStepResponse,
)
def get_org_onboarding_protocol_setup_step(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.ONBOARDING_READ, message="Insufficient permission to access onboarding validations"
    )
    context = build_user_auth_context(db, current_user)
    step = get_protocol_setup_step(db, org_id=_first_org_id(context))
    return ProtocolSetupStepResponse.model_validate(asdict(step))


@router.get("/org/mappings/summary", response_model=OrgMappingsSummaryResponse)
def get_org_mappings_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    return _build_org_mapping_summary(db, org_id=_first_org_id(context))


@router.get("/org/mappings/issues", response_model=OrgMappingsIssuesResponse)
def get_org_mappings_issues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    summary = _build_org_mapping_summary(db, org_id=_first_org_id(context))
    return _build_org_mapping_issues(summary)


@router.post("/org/onboarding/mark-step", response_model=OrgLaunchReadinessResponse)
def mark_org_onboarding_step(
    payload: OrgOnboardingStepUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.ONBOARDING_WRITE, message="Insufficient permission to manage onboarding validations"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    valid_steps = {item.key for item in STEP_DEFINITIONS}
    if payload.step_key not in valid_steps:
        raise HTTPException(status_code=422, detail="Unknown step_key")
    if payload.step_key == "export_validation" and payload.completed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "export_validation_requires_test_export",
                "message": "Use /org/onboarding/export-check to complete export validation with a test export.",
            },
        )
    if payload.step_key == "users_roles" and payload.completed:
        signals = collect_onboarding_signals(db, org_id=org_id)
        if signals.org_admin_count < 1 or signals.safety_capable_user_count < 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "users_roles_prerequisites_not_met",
                    "message": "Cannot complete users_roles step until role requirements are satisfied.",
                    "role_counts": _role_counts_for_org(db, org_id=org_id),
                    "violations": _role_violations(
                        role_counts=_role_counts_for_org(db, org_id=org_id)
                    ),
                },
            )
    set_step_completion_override(
        db,
        org_id=org_id,
        step_key=payload.step_key,
        is_completed=payload.completed,
        actor_user_id=current_user.id,
        source=payload.source,
    )
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.step.override",
        event_type="onboarding_readiness_override_updated",
        entity_type="onboarding_step",
        entity_id=payload.step_key,
        metadata={"completed": payload.completed, "source": payload.source},
    )
    readiness = get_org_onboarding_readiness(db, org_id=org_id)
    return _to_readiness_response(readiness)


@router.post(
    "/org/vehicles/import",
    response_model=VehicleImportJobCreateResponse,
    status_code=202,
)
def create_org_vehicle_import_job(
    payload: VehicleImportJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.IMPORTS_WRITE, message="Insufficient permission to manage imports"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    job = create_vehicle_import_job(db, org_id=org_id, provider=payload.provider)
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.vehicle_import.create",
        event_type="onboarding_vehicle_import_created",
        entity_type="vehicle_import_job",
        entity_id=str(job.job_id),
        metadata={"provider": payload.provider},
    )
    background_tasks.add_task(
        _run_vehicle_import_background,
        db,
        job_id=job.job_id,
        org_id=org_id,
        csv_content=payload.csv_content,
        header_mapping=payload.header_mapping,
        inactive_unit_numbers=payload.inactive_unit_numbers,
    )
    return VehicleImportJobCreateResponse(job_id=job.job_id, status=job.status)


@router.get(
    "/org/vehicles/import-jobs/{job_id}",
    response_model=VehicleImportJobResponse,
)
def get_org_vehicle_import_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.IMPORTS_READ, message="Insufficient permission to access imports"
    )
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(VehicleImportJob)
        .filter(
            VehicleImportJob.job_id == job_id,
            VehicleImportJob.org_id == _first_org_id(context),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return _to_vehicle_import_job_response(row)


@router.post(
    "/org/vehicles/{vehicle_id}/generate-qr",
    response_model=VehicleQrGenerateResponse,
)
def generate_vehicle_qr(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.VEHICLE_QR_WRITE, message="Insufficient permission to manage QR deployment"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    vehicle = _get_required_vehicle(db, org_id=org_id, vehicle_id=vehicle_id)

    active_token = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.adc_vehicle_id == vehicle.unit_number,
            VehicleQrToken.status == "active",
        )
        .first()
    )
    if active_token is None:
        active_token = VehicleQrToken(
            qr_token=secrets.token_urlsafe(32),
            org_id=org_id,
            adc_vehicle_id=vehicle.unit_number,
            status="active",
        )
        db.add(active_token)

    vehicle.qr_deployment_status = "generated"
    vehicle.qr_generated_at_utc = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(active_token.qr_token.encode()).hexdigest()
    _emit_vehicle_qr_event(
        db,
        org_id=org_id,
        actor_id=current_user.id,
        action="vehicle_qr_generated",
        vehicle_id=vehicle.unit_number,
        payload={"token_sha256": token_hash},
    )
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.vehicle_qr.generate",
        event_type="onboarding_vehicle_qr_generated",
        entity_type="vehicle",
        entity_id=vehicle.unit_number,
        metadata={"token_sha256": token_hash},
    )
    db.commit()
    return VehicleQrGenerateResponse(
        vehicle_id=vehicle.unit_number,
        qr_token=active_token.qr_token,
        deployment_status=vehicle.qr_deployment_status,
    )


@router.post(
    "/org/vehicles/bulk-generate-qr",
    response_model=VehicleQrBulkGenerateResponse,
)
def bulk_generate_vehicle_qr(
    payload: VehicleQrBulkGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.VEHICLE_QR_WRITE, message="Insufficient permission to manage QR deployment"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    generated: list[VehicleQrGenerateResponse] = []
    skipped: list[str] = []
    for vehicle_id in payload.vehicle_ids:
        vehicle = (
            db.query(OrgVehicleRegistry)
            .filter(
                OrgVehicleRegistry.org_id == org_id,
                OrgVehicleRegistry.unit_number == vehicle_id,
                OrgVehicleRegistry.is_active.is_(True),
            )
            .first()
        )
        if vehicle is None:
            skipped.append(vehicle_id)
            continue
        token = (
            db.query(VehicleQrToken)
            .filter(
                VehicleQrToken.org_id == org_id,
                VehicleQrToken.adc_vehicle_id == vehicle.unit_number,
                VehicleQrToken.status == "active",
            )
            .first()
        )
        if token is None:
            token = VehicleQrToken(
                qr_token=secrets.token_urlsafe(32),
                org_id=org_id,
                adc_vehicle_id=vehicle.unit_number,
                status="active",
            )
            db.add(token)
        vehicle.qr_deployment_status = "generated"
        vehicle.qr_generated_at_utc = datetime.now(timezone.utc)
        _emit_vehicle_qr_event(
            db,
            org_id=org_id,
            actor_id=current_user.id,
            action="vehicle_qr_generated",
            vehicle_id=vehicle.unit_number,
            payload={"bulk": True},
        )
        generated.append(
            VehicleQrGenerateResponse(
                vehicle_id=vehicle.unit_number,
                qr_token=token.qr_token,
                deployment_status="generated",
            )
        )
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.vehicle_qr.bulk_generate",
        event_type="onboarding_vehicle_qr_generated",
        entity_type="vehicle_qr_batch",
        metadata={"generated_count": len(generated), "skipped_count": len(skipped)},
    )
    db.commit()
    return VehicleQrBulkGenerateResponse(
        generated_count=len(generated),
        skipped_count=len(skipped),
        generated=generated,
        skipped_vehicle_ids=skipped,
    )


@router.post("/org/vehicles/{vehicle_id}/rotate-qr", response_model=VehicleQrGenerateResponse)
def rotate_vehicle_qr(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.VEHICLE_QR_WRITE, message="Insufficient permission to manage QR deployment"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    vehicle = _get_required_vehicle(db, org_id=org_id, vehicle_id=vehicle_id)
    active_tokens = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.adc_vehicle_id == vehicle.unit_number,
            VehicleQrToken.status == "active",
        )
        .all()
    )
    for row in active_tokens:
        row.status = "rotated"
    token = VehicleQrToken(
        qr_token=secrets.token_urlsafe(32),
        org_id=org_id,
        adc_vehicle_id=vehicle.unit_number,
        status="active",
        rotated_from_token=active_tokens[0].qr_token if active_tokens else None,
    )
    db.add(token)
    vehicle.qr_deployment_status = "generated"
    vehicle.qr_generated_at_utc = datetime.now(timezone.utc)
    _emit_vehicle_qr_event(
        db,
        org_id=org_id,
        actor_id=current_user.id,
        action=SystemEventType.VEHICLE_QR_ROTATED.value,
        vehicle_id=vehicle.unit_number,
        payload={"token_sha256": hashlib.sha256(token.qr_token.encode()).hexdigest()},
    )
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.vehicle_qr.rotate",
        event_type="onboarding_vehicle_qr_rotated",
        entity_type="vehicle",
        entity_id=vehicle.unit_number,
        metadata={"token_sha256": hashlib.sha256(token.qr_token.encode()).hexdigest()},
    )
    db.commit()
    return VehicleQrGenerateResponse(
        vehicle_id=vehicle.unit_number,
        qr_token=token.qr_token,
        deployment_status="generated",
    )


@router.get("/org/vehicles/{vehicle_id}/qr/printable")
def download_vehicle_qr_printable(
    vehicle_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.VEHICLE_QR_READ, message="Insufficient permission to access QR deployment"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    vehicle = _get_required_vehicle(db, org_id=org_id, vehicle_id=vehicle_id)
    token = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.org_id == org_id,
            VehicleQrToken.adc_vehicle_id == vehicle.unit_number,
            VehicleQrToken.status == "active",
        )
        .first()
    )
    if token is None:
        raise HTTPException(status_code=404, detail="QR token not generated for vehicle")
    vehicle.qr_deployment_status = "distributed"
    vehicle.qr_distributed_at_utc = datetime.now(timezone.utc)
    pdf_bytes = render_pdf(
        "vehicle_qr_printable",
        {
            "vehicle_id": vehicle.unit_number,
            "qr_token": token.qr_token,
            "qr_image_data_uri": qr_png_data_uri(token.qr_token),
        },
    )
    _emit_vehicle_qr_event(
        db,
        org_id=org_id,
        actor_id=current_user.id,
        action="vehicle_qr_distributed",
        vehicle_id=vehicle.unit_number,
        payload={"artifact_type": "printable_pdf"},
    )
    db.commit()
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="vehicle-{vehicle.unit_number}-qr.pdf"'
            )
        },
    )


@router.get("/org/onboarding/qr-stats", response_model=VehicleQrStatsResponse)
def get_org_onboarding_qr_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.READINESS_VIEW, message="Insufficient permission to view onboarding readiness"
    )
    context = build_user_auth_context(db, current_user)
    return _vehicle_qr_stats(db, org_id=_first_org_id(context))


@router.post(
    "/org/drivers/import",
    response_model=DriverImportJobCreateResponse,
    status_code=202,
)
def create_org_driver_import_job(
    payload: DriverImportJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.IMPORTS_WRITE, message="Insufficient permission to manage imports"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    job = create_driver_import_job(db, org_id=org_id, provider=payload.provider)
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="onboarding.driver_import.create",
        event_type="onboarding_driver_import_created",
        entity_type="driver_import_job",
        entity_id=str(job.job_id),
        metadata={"provider": payload.provider},
    )
    background_tasks.add_task(
        _run_driver_import_background,
        db,
        job_id=job.job_id,
        org_id=org_id,
        csv_content=payload.csv_content,
        header_mapping=payload.header_mapping,
        inactive_mobile_phones=payload.inactive_mobile_phones,
    )
    return DriverImportJobCreateResponse(job_id=job.job_id, status=job.status)


@router.get(
    "/org/drivers/import-jobs/{job_id}",
    response_model=DriverImportJobResponse,
)
def get_org_driver_import_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.IMPORTS_READ, message="Insufficient permission to access imports"
    )
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(DriverImportJob)
        .filter(
            DriverImportJob.job_id == job_id,
            DriverImportJob.org_id == _first_org_id(context),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return _to_driver_import_job_response(row)


@router.get("/org/users", response_model=OrgUsersResponse)
def list_org_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.USER_MANAGEMENT_READ, message="Insufficient permission to access user management"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    users = (
        db.query(User)
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(UserOrg.org_id == org_id)
        .order_by(User.created_at_utc.asc())
        .all()
    )
    invites = (
        db.query(OrgUserInvite)
        .filter(OrgUserInvite.org_id == org_id)
        .order_by(OrgUserInvite.created_at_utc.desc())
        .all()
    )
    role_counts = _role_counts_for_org(db, org_id=org_id)
    return OrgUsersResponse(
        users=[
            OrgUserSummary(
                user_id=row.id,
                email=row.email,
                role=normalize_role(row.role).value,
                is_active=bool(row.is_active),
                created_at_utc=row.created_at_utc,
            )
            for row in users
        ],
        invites=[
            OrgUserInviteSummary(
                invite_id=row.invite_id,
                email=row.email,
                role=normalize_role(row.role).value,
                status=row.status,
                created_at_utc=row.created_at_utc,
                last_sent_at_utc=row.last_sent_at_utc,
                deactivated_at_utc=row.deactivated_at_utc,
            )
            for row in invites
        ],
        role_counts=role_counts,
        violations=_role_violations(role_counts=role_counts),
    )


@router.post("/org/users/invite", response_model=OrgInviteUserResponse, status_code=201)
def invite_org_user(
    payload: OrgInviteUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_org_user_admin),
):
    _require_phase6_capability(
        current_user, Capability.USER_MANAGEMENT_WRITE, message="Insufficient permission to manage users"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    invite = OrgUserInvite(
        org_id=org_id,
        email=payload.email.lower(),
        role=normalize_role(payload.role).value,
        status="pending",
        invited_by_user_id=current_user.id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="org.users.invite",
        event_type="org_user_invite_created",
        entity_type="org_user_invite",
        entity_id=str(invite.invite_id),
        metadata={"email": invite.email, "role": invite.role, "status": invite.status},
    )
    role_counts = _role_counts_for_org(db, org_id=org_id)
    return OrgInviteUserResponse(
        invite=OrgUserInviteSummary(
            invite_id=invite.invite_id,
            email=invite.email,
            role=normalize_role(invite.role).value,
            status=invite.status,
            created_at_utc=invite.created_at_utc,
            last_sent_at_utc=invite.last_sent_at_utc,
            deactivated_at_utc=invite.deactivated_at_utc,
        ),
        role_counts=role_counts,
        violations=_role_violations(role_counts=role_counts),
    )


@router.patch("/org/users/{user_id}/role", response_model=OrgUsersResponse)
def patch_org_user_role(
    user_id: uuid.UUID,
    payload: OrgPatchUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_org_user_admin),
):
    _require_phase6_capability(
        current_user, Capability.USER_MANAGEMENT_WRITE, message="Insufficient permission to manage users"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    row = (
        db.query(User)
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(UserOrg.org_id == org_id, User.id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    previous_role = row.role
    row.role = normalize_role(payload.role).value
    db.add(row)
    db.commit()
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="org.users.role.patch",
        event_type="org_user_role_changed",
        entity_type="user",
        entity_id=str(row.id),
        metadata={"previous_role": previous_role, "new_role": row.role},
    )
    return list_org_users(db=db, current_user=current_user)


@router.post(
    "/org/users/invite/{invite_id}/resend", response_model=OrgInviteUserResponse
)
def resend_org_user_invite(
    invite_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(_org_user_admin),
):
    _require_phase6_capability(
        current_user, Capability.USER_MANAGEMENT_WRITE, message="Insufficient permission to manage users"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    row = (
        db.query(OrgUserInvite)
        .filter(OrgUserInvite.invite_id == invite_id, OrgUserInvite.org_id == org_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Invite is not active")
    row.last_sent_at_utc = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="org.users.invite.resend",
        event_type="org_user_invite_resent",
        entity_type="org_user_invite",
        entity_id=str(row.invite_id),
        metadata={"email": row.email, "role": row.role},
    )
    role_counts = _role_counts_for_org(db, org_id=org_id)
    return OrgInviteUserResponse(
        invite=OrgUserInviteSummary(
            invite_id=row.invite_id,
            email=row.email,
            role=normalize_role(row.role).value,
            status=row.status,
            created_at_utc=row.created_at_utc,
            last_sent_at_utc=row.last_sent_at_utc,
            deactivated_at_utc=row.deactivated_at_utc,
        ),
        role_counts=role_counts,
        violations=_role_violations(role_counts=role_counts),
    )


@router.post(
    "/org/users/invite/{invite_id}/deactivate", response_model=OrgInviteUserResponse
)
def deactivate_org_user_invite(
    invite_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(_org_user_admin),
):
    _require_phase6_capability(
        current_user, Capability.USER_MANAGEMENT_WRITE, message="Insufficient permission to manage users"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    row = (
        db.query(OrgUserInvite)
        .filter(OrgUserInvite.invite_id == invite_id, OrgUserInvite.org_id == org_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    row.status = "deactivated"
    row.deactivated_at_utc = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="org.users.invite.deactivate",
        event_type="org_user_invite_deactivated",
        entity_type="org_user_invite",
        entity_id=str(row.invite_id),
        metadata={"email": row.email, "role": row.role},
    )
    role_counts = _role_counts_for_org(db, org_id=org_id)
    return OrgInviteUserResponse(
        invite=OrgUserInviteSummary(
            invite_id=row.invite_id,
            email=row.email,
            role=normalize_role(row.role).value,
            status=row.status,
            created_at_utc=row.created_at_utc,
            last_sent_at_utc=row.last_sent_at_utc,
            deactivated_at_utc=row.deactivated_at_utc,
        ),
        role_counts=role_counts,
        violations=_role_violations(role_counts=role_counts),
    )


@router.get(
    "/org/integrations", response_model=list[IntegrationConnectionHealthResponse]
)
def list_org_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.INTEGRATIONS_READ, message="Insufficient permission to access integrations"
    )
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(IntegrationConnection)
        .filter(IntegrationConnection.org_id.in_(context.org_ids))
        .order_by(IntegrationConnection.updated_at_utc.desc())
        .all()
    )
    return [
        IntegrationConnectionHealthResponse(
            integration_id=row.connection_id,
            provider=row.provider,
            domain=row.domain,
            status=row.status,
            healthy=row.status in {"active", "pending"},
            reason=None
            if row.status in {"active", "pending"}
            else "Connection not healthy",
            last_synced_at_utc=row.last_synced_at_utc,
            updated_at_utc=row.updated_at_utc,
        )
        for row in rows
    ]


@router.post(
    "/org/integrations",
    response_model=IntegrationConnectionHealthResponse,
)
def upsert_org_integration(
    payload: IntegrationConnectionUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_integration_admin),
):
    _require_phase6_capability(
        current_user, Capability.INTEGRATIONS_WRITE, message="Insufficient permission to manage integrations"
    )
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.org_id == org_id,
            IntegrationConnection.provider == payload.provider,
            IntegrationConnection.domain == payload.domain,
        )
        .first()
    )
    if row is None:
        row = IntegrationConnection(
            org_id=org_id,
            provider=payload.provider,
            domain=payload.domain,
        )

    row.status = payload.status
    row.credentials_ref = payload.credentials_ref
    row.config_json = payload.config_json
    credential_changed = bool(payload.credentials_ref)
    db.add(row)
    db.commit()
    db.refresh(row)
    _emit_org_audit(
        db,
        org_id=org_id,
        actor=current_user,
        action="integration.connection.upsert",
        event_type="integration_credentials_updated" if credential_changed else "integration_connection_updated",
        entity_type="integration_connection",
        entity_id=str(row.connection_id),
        metadata={
            "provider": row.provider,
            "domain": row.domain,
            "status": row.status,
            "credentials_ref_set": bool(row.credentials_ref),
        },
    )

    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=row.status in {"active", "pending"},
        reason=None
        if row.status in {"active", "pending"}
        else "Connection not healthy",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.get(
    "/org/integrations/validation-results",
    response_model=list[IntegrationValidationResultResponse],
)
def list_org_integration_validation_results(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.READINESS_VIEW, message="Insufficient permission to view onboarding readiness"
    )
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(IntegrationValidationResult)
        .filter(IntegrationValidationResult.org_id.in_(context.org_ids))
        .order_by(IntegrationValidationResult.validated_at_utc.desc())
        .all()
    )
    return [
        IntegrationValidationResultResponse(
            integration_id=row.connection_id,
            credentialStatus=row.credential_status,
            capabilityStatus=row.capability_status,
            mappingStatus=row.mapping_status,
            messages=list(row.messages_json or []),
            timestamp=row.validated_at_utc,
        )
        for row in rows
    ]


@router.get(
    "/internal/audit/events",
    response_model=list[AuditSearchResponseItem],
)
def list_internal_audit_events(
    org_id: uuid.UUID | None = None,
    action: str | None = None,
    event_type: str | None = None,
    outcome: str | None = None,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    lookback_hours: int = 168,
    limit: int = 250,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    if normalize_role(context.user.role) != Role.SYSTEM_ADMIN:
        raise HTTPException(status_code=403, detail="System admin access required")

    lookback_cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, lookback_hours))
    query = db.query(AuditEvent).filter(AuditEvent.occurred_at_utc >= lookback_cutoff)
    if org_id is not None:
        query = query.filter(AuditEvent.org_id == org_id)
    if action:
        query = query.filter(AuditEvent.action.ilike(f"%{action}%"))
    if event_type:
        query = query.filter(AuditEvent.event_type.ilike(f"%{event_type}%"))
    if outcome:
        query = query.filter(AuditEvent.outcome == outcome)
    if actor_id:
        query = query.filter(AuditEvent.actor_id.ilike(f"%{actor_id}%"))
    rows = query.order_by(AuditEvent.occurred_at_utc.desc()).limit(max(1, min(limit, 1000))).all()

    filtered_rows = rows
    if entity_type or entity_id:
        filtered_rows = []
        for row in rows:
            metadata = row.metadata_json or {}
            entity = metadata.get("entity", {}) if isinstance(metadata, dict) else {}
            if entity_type and entity.get("type") != entity_type:
                continue
            if entity_id and entity.get("id") != entity_id:
                continue
            filtered_rows.append(row)

    return [
        AuditSearchResponseItem(
            audit_event_id=row.id,
            org_id=row.org_id,
            incident_id=row.incident_id,
            export_id=row.export_id,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            action=row.action,
            event_type=row.event_type,
            outcome=row.outcome,
            occurred_at_utc=row.occurred_at_utc,
            metadata=row.metadata_json or {},
        )
        for row in filtered_rows
    ]


@router.get(
    "/org/integrations/{integration_id}",
    response_model=IntegrationConnectionHealthResponse,
)
def get_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.INTEGRATIONS_READ, message="Insufficient permission to access integrations"
    )
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=row.status in {"active", "pending"},
        reason=None
        if row.status in {"active", "pending"}
        else "Connection not healthy",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.post(
    "/org/integrations/{integration_id}/validate",
    response_model=IntegrationConnectionValidateResponse,
)
def validate_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(_integration_admin),
):
    _require_phase6_capability(
        current_user, Capability.INTEGRATIONS_WRITE, message="Insufficient permission to manage integrations"
    )
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    (
        credential_status,
        capability_status,
        mapping_status,
        messages,
        valid,
        message,
    ) = _evaluate_integration_validation(db=db, org_id=row.org_id, row=row)
    validation = IntegrationValidationResult(
        org_id=row.org_id,
        connection_id=row.connection_id,
        credential_status=credential_status,
        capability_status=capability_status,
        mapping_status=mapping_status,
        messages_json=messages,
        validated_at_utc=datetime.now(timezone.utc),
    )
    db.add(validation)
    db.commit()
    _emit_org_audit(
        db,
        org_id=row.org_id,
        actor=current_user,
        action="integration.connection.validate",
        event_type="integration_validation_completed",
        entity_type="integration_connection",
        entity_id=str(row.connection_id),
        outcome="success" if valid else "failure",
        metadata={
            "provider": row.provider,
            "domain": row.domain,
            "credential_status": credential_status,
            "capability_status": capability_status,
            "mapping_status": mapping_status,
            "messages": messages,
        },
    )

    return IntegrationConnectionValidateResponse(
        integration_id=row.connection_id,
        valid=valid,
        status=row.status,
        message=message,
        credentialStatus=credential_status,
        capabilityStatus=capability_status,
        mappingStatus=mapping_status,
        messages=messages,
        timestamp=validation.validated_at_utc,
    )


@router.patch(
    "/org/integrations/{integration_id}",
    response_model=IntegrationConnectionHealthResponse,
)
def patch_org_integration(
    integration_id: uuid.UUID,
    payload: IntegrationConnectionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.INTEGRATIONS_WRITE, message="Insufficient permission to manage integrations"
    )
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    updates = payload.model_dump(exclude_unset=True)
    previous_credentials_ref = row.credentials_ref
    for field in ("status", "credentials_ref", "config_json"):
        if field in updates:
            setattr(row, field, updates[field])
    db.add(row)
    db.commit()
    db.refresh(row)
    _emit_org_audit(
        db,
        org_id=row.org_id,
        actor=current_user,
        action="integration.connection.patch",
        event_type=(
            "integration_credentials_updated"
            if "credentials_ref" in updates and updates.get("credentials_ref") != previous_credentials_ref
            else "integration_connection_updated"
        ),
        entity_type="integration_connection",
        entity_id=str(row.connection_id),
        metadata={"updated_fields": sorted(updates.keys()), "status": row.status},
    )

    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=row.status in {"active", "pending"},
        reason=None
        if row.status in {"active", "pending"}
        else "Connection not healthy",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.post(
    "/org/integrations/{integration_id}/disable",
    response_model=IntegrationConnectionHealthResponse,
)
def disable_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_phase6_capability(
        current_user, Capability.INTEGRATIONS_WRITE, message="Insufficient permission to manage integrations"
    )
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    row.status = "inactive"
    db.add(row)
    db.commit()
    db.refresh(row)
    _emit_org_audit(
        db,
        org_id=row.org_id,
        actor=current_user,
        action="integration.connection.disable",
        event_type="integration_connection_updated",
        entity_type="integration_connection",
        entity_id=str(row.connection_id),
        metadata={"status": row.status},
    )

    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=False,
        reason="Connection disabled",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.get(
    "/integration-operations",
    response_model=list[IntegrationOperationDiagnosticsResponse],
)
def list_integration_operations(
    incident_id: uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_integration_admin),
):
    context = build_user_auth_context(db, current_user)
    query = db.query(IntegrationOperation).filter(
        IntegrationOperation.org_id.in_(context.org_ids)
    )
    if incident_id is not None:
        query = query.filter(IntegrationOperation.incident_id == incident_id)
    if status is not None:
        query = query.filter(IntegrationOperation.status == status)
    if provider is not None:
        query = query.filter(IntegrationOperation.provider == provider)
    rows = query.order_by(IntegrationOperation.requested_at_utc.desc()).all()
    return [_to_diagnostics_response(row) for row in rows]


@router.get(
    "/integration-operations/{operation_id}",
    response_model=IntegrationOperationDiagnosticsResponse,
)
def get_integration_operation(
    operation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(_integration_admin),
):
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationOperation)
        .filter(
            IntegrationOperation.operation_id == operation_id,
            IntegrationOperation.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration operation not found")
    return _to_diagnostics_response(row)


def _to_diagnostics_response(
    row: IntegrationOperation,
) -> IntegrationOperationDiagnosticsResponse:
    response = IntegrationOperationDiagnosticsResponse.model_validate(
        row, from_attributes=True
    )
    response.payload_json = redact_payload_for_storage(response.payload_json)
    response.result_json = redact_payload_for_storage(response.result_json)
    return response


@router.get(
    "/incidents/{incident_id}/evidence-requests",
    response_model=list[EvidenceRequestSummary],
)
def list_incident_evidence_requests(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(EvidenceRequest)
        .filter(
            EvidenceRequest.incident_id == incident_id,
            EvidenceRequest.org_id.in_(context.org_ids),
        )
        .order_by(EvidenceRequest.requested_at_utc.desc())
        .all()
    )
    return [
        EvidenceRequestSummary.model_validate(row, from_attributes=True) for row in rows
    ]


@router.post(
    "/incidents/{incident_id}/evidence-requests/retry",
    response_model=EvidenceRetryActionResponse,
)
def retry_incident_evidence_requests(
    incident_id: uuid.UUID,
    payload: EvidenceRetryActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    query = db.query(EvidenceRequest).filter(
        EvidenceRequest.incident_id == incident_id,
        EvidenceRequest.org_id.in_(context.org_ids),
    )
    if payload.evidence_request_ids:
        query = query.filter(
            EvidenceRequest.evidence_request_id.in_(payload.evidence_request_ids)
        )
    if payload.retry_failed_only:
        query = query.filter(EvidenceRequest.status == "failed")

    rows = query.order_by(EvidenceRequest.requested_at_utc.desc()).all()
    if not rows:
        return EvidenceRetryActionResponse(
            incident_id=incident_id, retried_count=0, queued_operation_ids=[]
        )

    correlation_id = get_request_id() or str(uuid.uuid4())
    operation_ids: list[uuid.UUID] = []

    dashcam_ids = [row.evidence_request_id for row in rows if row.domain == "dashcam"]
    telematics_ids = [
        row.evidence_request_id for row in rows if row.domain == "telematics"
    ]
    org_id = rows[0].org_id
    if org_id is None:
        raise HTTPException(
            status_code=422, detail="Evidence requests are missing org_id"
        )

    if dashcam_ids:
        operation_ids.append(
            queue_dashcam_capture(
                db,
                org_id=org_id,
                incident_id=incident_id,
                window_start=None,
                window_end=None,
                api_correlation_id=correlation_id,
                evidence_request_ids=dashcam_ids,
            )
        )
    if telematics_ids:
        operation_ids.append(
            queue_telematics_capture(
                db,
                org_id=org_id,
                incident_id=incident_id,
                window_start=None,
                window_end=None,
                api_correlation_id=correlation_id,
                evidence_request_ids=telematics_ids,
            )
        )

    return EvidenceRetryActionResponse(
        incident_id=incident_id,
        retried_count=len(rows),
        queued_operation_ids=operation_ids,
    )


@router.get(
    "/incidents/{incident_id}/evidence-summary", response_model=EvidenceSummaryResponse
)
def get_incident_evidence_summary(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(EvidenceRequest)
        .filter(
            EvidenceRequest.incident_id == incident_id,
            EvidenceRequest.org_id.in_(context.org_ids),
        )
        .order_by(EvidenceRequest.requested_at_utc.desc())
        .all()
    )

    status_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    retryable_failures = 0
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
        provider_counts[row.provider] = provider_counts.get(row.provider, 0) + 1
        if row.status == "failed" and row.error_retryable:
            retryable_failures += 1

    return EvidenceSummaryResponse(
        incident_id=incident_id,
        total_requests=len(rows),
        status_counts=status_counts,
        provider_counts=provider_counts,
        retryable_failures=retryable_failures,
        requests=[
            EvidenceRequestSummary.model_validate(row, from_attributes=True)
            for row in rows
        ],
    )


@router.post("/provider-webhooks/twilio/voice")
async def provider_twilio_voice_webhook(
    request: Request, db: Session = Depends(get_db)
):
    raw_body = await request.body()
    params = parse_form_encoded_body(raw_body)
    signature_valid, signature_error = validate_twilio_signature(
        auth_token=settings.TWILIO_AUTH_TOKEN,
        request_url=str(request.url),
        params=params,
        provided_signature=request.headers.get("X-Twilio-Signature"),
    )
    result = persist_twilio_voice_callback(
        db,
        payload=params,
        raw_payload=raw_body.decode("utf-8", errors="ignore"),
        signature_valid=signature_valid,
        signature_error=signature_error,
    )
    return Response(
        status_code=result.status_code, content=result.body.get("detail", "ok")
    )


@router.post("/provider-webhooks/twilio/status")
async def provider_twilio_status_webhook(
    request: Request, db: Session = Depends(get_db)
):
    raw_body = await request.body()
    params = parse_form_encoded_body(raw_body)
    signature_valid, signature_error = validate_twilio_signature(
        auth_token=settings.TWILIO_AUTH_TOKEN,
        request_url=str(request.url),
        params=params,
        provided_signature=request.headers.get("X-Twilio-Signature"),
    )
    result = process_twilio_status_callback(
        db,
        payload=params,
        raw_payload=raw_body.decode("utf-8", errors="ignore"),
        signature_valid=signature_valid,
        signature_error=signature_error,
    )
    return result.body
