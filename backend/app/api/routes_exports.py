"""Export API routes."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DownloadExportResponse
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.db.repo.exports import get_export
from app.db.repo.events import create_event
from app.domain.system_event_types import SystemEventType
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def list_exports_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return []


@router.get("/{export_id}")
def get_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    export = get_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    return {
        "export_id": str(export.export_id),
        "incident_id": str(export.incident_id),
        "status": export.status,
    }


@router.get("/{export_id}/download", response_model=DownloadExportResponse)
def download_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    export = get_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if export.status != "ready":
        raise HTTPException(status_code=409, detail="Export is not ready")

    # Build a presigned-style URL (placeholder — real impl uses boto3)
    bucket = export.s3_bucket or settings.S3_BUCKET
    key = export.s3_key or f"exports/{export.export_id}.zip"
    presigned_url = (
        f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
        f"?X-Amz-Expires=3600"
    )

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
