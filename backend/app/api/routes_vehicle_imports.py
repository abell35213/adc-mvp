"""Vehicle import workflow routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.api.error_responses import raise_api_error
from app.api.schemas import (
    ApiErrorResponse,
    ImportJobStatus,
    VehicleImportJobCreateRequest,
    VehicleImportJobCreateResponse,
    VehicleImportJobResponse,
)
from app.core.deps import get_current_user
from app.db.models import User, VehicleImportJob
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability
from app.services.vehicle_import_service import create_vehicle_import_job, run_vehicle_import_job

router = APIRouter(prefix="/org/vehicles", tags=["vehicle-imports"])


def _first_org_id(user_context) -> uuid.UUID:
    return user_context.org_ids[0]


def _require_vehicle_import_access(user: User, *, write: bool = False) -> None:
    capability = Capability.INCIDENT_WRITE if write else Capability.INCIDENT_READ
    if not has_capability(user.role, capability):
        raise_api_error(
            status_code=403,
            message="You do not have permission to manage vehicle imports.",
            code="ACCESS_DENIED",
        )


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
        inactive_unit_numbers={item.strip().lower() for item in inactive_unit_numbers if item.strip()},
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


@router.post(
    "/import",
    response_model=VehicleImportJobCreateResponse,
    status_code=202,
    responses={403: {"model": ApiErrorResponse}},
    summary="Create vehicle CSV import job",
)
def create_org_vehicle_import_job(
    payload: VehicleImportJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_vehicle_import_access(current_user, write=True)
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
    "/import-jobs",
    response_model=list[VehicleImportJobResponse],
    responses={403: {"model": ApiErrorResponse}},
    summary="List vehicle import jobs",
)
def list_org_vehicle_import_jobs(
    status: ImportJobStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_vehicle_import_access(current_user)
    context = build_user_auth_context(db, current_user)
    query = db.query(VehicleImportJob).filter(VehicleImportJob.org_id == _first_org_id(context))
    if status is not None:
        query = query.filter(VehicleImportJob.status == status)
    rows = query.order_by(VehicleImportJob.created_at_utc.desc()).offset(offset).limit(limit).all()
    return [_to_vehicle_import_job_response(row) for row in rows]


@router.get(
    "/import-jobs/{job_id}",
    response_model=VehicleImportJobResponse,
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Get vehicle import job detail",
)
def get_org_vehicle_import_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_vehicle_import_access(current_user)
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(VehicleImportJob)
        .filter(VehicleImportJob.job_id == job_id, VehicleImportJob.org_id == _first_org_id(context))
        .first()
    )
    if row is None:
        raise_api_error(status_code=404, message="Import job not found.", code="RESOURCE_NOT_FOUND")
    return _to_vehicle_import_job_response(row)
