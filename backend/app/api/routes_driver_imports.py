"""Driver import workflow routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.api.error_responses import raise_api_error
from app.api.schemas import (
    ApiErrorResponse,
    DriverImportJobCreateRequest,
    DriverImportJobCreateResponse,
    DriverImportJobResponse,
    ImportJobStatus,
)
from app.core.deps import get_current_user
from app.db.models import DriverImportJob, User
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability
from app.services.driver_import_service import create_driver_import_job, run_driver_import_job
from app.services.phone_normalize import normalize_phone

router = APIRouter(prefix="/org/drivers", tags=["driver-imports"])


def _first_org_id(user_context) -> uuid.UUID:
    return user_context.org_ids[0]


def _require_driver_import_access(user: User, *, write: bool = False) -> None:
    capability = Capability.INCIDENT_WRITE if write else Capability.INCIDENT_READ
    if not has_capability(user.role, capability):
        raise_api_error(
            status_code=403,
            message="You do not have permission to manage driver imports.",
            code="ACCESS_DENIED",
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


@router.post(
    "/import",
    response_model=DriverImportJobCreateResponse,
    status_code=202,
    responses={403: {"model": ApiErrorResponse}},
    summary="Create driver CSV import job",
)
def create_org_driver_import_job(
    payload: DriverImportJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_driver_import_access(current_user, write=True)
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
    "/import-jobs",
    response_model=list[DriverImportJobResponse],
    responses={403: {"model": ApiErrorResponse}},
    summary="List driver import jobs",
)
def list_org_driver_import_jobs(
    status: ImportJobStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_driver_import_access(current_user)
    context = build_user_auth_context(db, current_user)
    query = db.query(DriverImportJob).filter(DriverImportJob.org_id == _first_org_id(context))
    if status is not None:
        query = query.filter(DriverImportJob.status == status)
    rows = query.order_by(DriverImportJob.created_at_utc.desc()).offset(offset).limit(limit).all()
    return [_to_driver_import_job_response(row) for row in rows]


@router.get(
    "/import-jobs/{job_id}",
    response_model=DriverImportJobResponse,
    responses={403: {"model": ApiErrorResponse}, 404: {"model": ApiErrorResponse}},
    summary="Get driver import job detail",
)
def get_org_driver_import_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_driver_import_access(current_user)
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(DriverImportJob)
        .filter(DriverImportJob.job_id == job_id, DriverImportJob.org_id == _first_org_id(context))
        .first()
    )
    if row is None:
        raise_api_error(status_code=404, message="Import job not found.", code="RESOURCE_NOT_FOUND")
    return _to_driver_import_job_response(row)
