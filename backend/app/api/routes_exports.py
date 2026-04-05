"""Export API routes."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DownloadExportResponse
from app.core.deps import get_current_user
from app.core.logging import set_log_context
from app.core.metrics import MetricNames, increment, timed
from app.db.models import User
from app.db.session import get_db
from app.db.repo.exports import get_export, list_exports_for_org_ids
from app.db.repo.events import create_event
from app.db.repo.incidents import get_incident
from app.domain.system_event_types import SystemEventType
from app.core.config import settings
from app.services.vault_s3 import (
    S3PresignConfigurationError,
    S3PresignGenerationError,
    generate_presigned_download_url,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_export_owner_org_id(db: Session, export):
    """Resolve org ownership for an export, including legacy null-org rows."""
    if export.org_id is not None:
        return export.org_id

    incident = get_incident(db, export.incident_id)
    if incident is None:
        return None
    return incident.org_id


@router.get("/")
def list_exports_endpoint(
    db: Session = Depends(get_db),
    org_ids: list[uuid.UUID] = Depends(get_current_user_org_ids),
    current_user: User = Depends(get_current_user),
):
    org_ids = get_user_org_ids(db, current_user.id)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )
    exports = list_exports_for_org_ids(db, org_ids)
    return [
        {
            "export_id": str(export.export_id),
            "incident_id": str(export.incident_id),
            "status": export.status,
            "created_at_utc": export.created_at_utc,
        }
        for export in exports
    ]


@router.get("/{export_id}")
def get_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    org_ids: list[uuid.UUID] = Depends(get_current_user_org_ids),
    current_user: User = Depends(get_current_user),
):
    org_ids = get_user_org_ids(db, current_user.id)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )
    export = get_export(db, export_id)
    if not export:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(status_code=404, detail="Export not found")

    export_org_id = _get_export_owner_org_id(db, export)
    if export_org_id is None or export_org_id not in org_ids:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "export_id": str(export.export_id),
        "incident_id": str(export.incident_id),
        "status": export.status,
    }


@router.get("/{export_id}/download", response_model=DownloadExportResponse)
def download_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    org_ids: list[uuid.UUID] = Depends(get_current_user_org_ids),
    current_user: User = Depends(get_current_user),
):
    increment(MetricNames.EXPORT_DOWNLOAD_ATTEMPTS)
    with timed(MetricNames.EXPORT_DOWNLOAD_ATTEMPTS):
        org_ids = get_user_org_ids(db, current_user.id)
        set_log_context(
            user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
        )
        export = get_export(db, export_id)
    if not export:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(status_code=404, detail="Export not found")

    export_org_id = _get_export_owner_org_id(db, export)
    if export_org_id is None or export_org_id not in org_ids:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(status_code=403, detail="Forbidden")

    if export.status != "ready":
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(status_code=409, detail="Export is not ready")

    bucket = export.s3_bucket or settings.S3_BUCKET
    key = export.s3_key or f"exports/{export.export_id}.zip"
    expires_in_seconds = 3600

    try:
        presigned_url = generate_presigned_download_url(
            bucket=bucket,
            key=key,
            region=settings.AWS_REGION,
            expires_in=expires_in_seconds,
        )
    except S3PresignConfigurationError as exc:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except S3PresignGenerationError as exc:
        increment(MetricNames.EXPORT_DOWNLOAD_FAILURES)
        raise HTTPException(
            status_code=502,
            detail="Unable to generate export download URL",
        ) from exc

    create_event(
        db,
        incident_id=export.incident_id,
        event_type=SystemEventType.EXPORT_DOWNLOADED,
        actor_type="system",
        actor_id="api",
        payload={"export_id": str(export.export_id)},
    )

    return DownloadExportResponse(
        export_id=export.export_id,
        url=presigned_url,
        status="ready",
    )
