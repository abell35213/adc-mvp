"""Integration and evidence diagnostics API routes."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import secrets

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

from app.api.schemas import (
    DriverImportJobCreateRequest,
    DriverImportJobCreateResponse,
    DriverImportJobResponse,
    EvidenceRequestSummary,
    EvidenceRetryActionRequest,
    EvidenceRetryActionResponse,
    EvidenceSummaryResponse,
    IntegrationConnectionHealthResponse,
    IntegrationConnectionUpdateRequest,
    IntegrationConnectionValidateResponse,
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
    OrgUserInvite,
    Org,
    User,
    UserOrg,
    DriverImportJob,
    Driver,
    DriverVehicleAssignment,
    ExternalMapping,
    OrgVehicleRegistry,
    VehicleImportJob,
    VehicleQrToken,
    Event,
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
    collect_onboarding_signals,
    get_protocol_setup_step,
    get_org_onboarding_readiness,
    set_step_completion_override,
)
from app.security.permissions import (
    CANONICAL_ROLES,
    Capability,
    has_capability,
    normalize_role,
)
from app.domain.system_event_types import SystemEventType
from app.services.pdf_render import render_pdf

router = APIRouter()

_integration_admin = require_user_role("system_admin", "org_admin")
_org_user_admin = require_user_role("system_admin", "org_admin")
_PILOT_MIN_MAPPED_DRIVERS = 3
_PILOT_MIN_MAPPED_VEHICLES = 3
_ASSIGNMENT_CONFIDENCE_MEDIUM_THRESHOLD = 0.7
_ASSIGNMENT_CONFIDENCE_HIGH_THRESHOLD = 0.9


def _first_org_id(context) -> uuid.UUID:
    return context.org_ids[0]


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
            "snapshot_created_at_utc": readiness.snapshot_created_at_utc,
        }
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
    context = build_user_auth_context(db, current_user)
    readiness = get_org_onboarding_readiness(db, org_id=_first_org_id(context))
    return _to_readiness_response(readiness)


@router.get(
    "/org/onboarding/protocol-setup-step",
    response_model=ProtocolSetupStepResponse,
)
def get_org_onboarding_protocol_setup_step(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    valid_steps = {item.key for item in STEP_DEFINITIONS}
    if payload.step_key not in valid_steps:
        raise HTTPException(status_code=422, detail="Unknown step_key")
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
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    job = create_vehicle_import_job(db, org_id=org_id, provider=payload.provider)
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
        {"vehicle_id": vehicle.unit_number, "qr_token": token.qr_token},
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
    context = build_user_auth_context(db, current_user)
    org_id = _first_org_id(context)
    job = create_driver_import_job(db, org_id=org_id, provider=payload.provider)
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
    row.role = normalize_role(payload.role).value
    db.add(row)
    db.commit()
    return list_org_users(db=db, current_user=current_user)


@router.post(
    "/org/users/invite/{invite_id}/resend", response_model=OrgInviteUserResponse
)
def resend_org_user_invite(
    invite_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(_org_user_admin),
):
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


@router.get(
    "/org/integrations/{integration_id}",
    response_model=IntegrationConnectionHealthResponse,
)
def get_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    valid = bool(row.credentials_ref) and row.status != "inactive"
    return IntegrationConnectionValidateResponse(
        integration_id=row.connection_id,
        valid=valid,
        status=row.status,
        message="Connection validated"
        if valid
        else "Connection missing credentials or disabled",
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
    for field in ("status", "credentials_ref", "config_json"):
        if field in updates:
            setattr(row, field, updates[field])
    db.add(row)
    db.commit()
    db.refresh(row)

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
