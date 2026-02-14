"""Export API routes.

This module exposes endpoints for listing export packages, retrieving
metadata for a single export, and downloading completed export archives.

The existing implementation returned an empty list for ``list_exports_endpoint``
and used a placeholder pre‑signed URL for downloads. The new implementation
performs real database queries to list the exports available to the current
user based on their organization(s), and leverages the VaultS3 service to
generate pre‑signed download URLs. A download event is recorded whenever
a user fetches an export URL.
"""

from __future__ import annotations

import uuid
import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import (
    DownloadExportResponse,
    ExportSummary,
)
from app.core.deps import get_current_user
from app.db.models import Export, Incident, User
from app.db.session import get_db
from app.db.repo.exports import get_export
from app.db.repo.events import create_event
from app.db.repo.users import get_user_org_ids
from app.domain.system_event_types import SystemEventType
from app.core.config import settings
from app.services.vault_s3 import VaultS3

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[ExportSummary])
def list_exports_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all exports belonging to incidents within the current user's organizations.

    An export is only visible to users whose organizations match the export's
    owning incident. The returned list contains minimal metadata suitable for
    summarising exports on the dashboard. If no exports are found, an empty
    list is returned.
    """
    org_ids = get_user_org_ids(db, current_user.id)
    if not org_ids:
        return []

    # Query exports by joining incidents to filter on org_id. We use
    # joinedload to avoid N+1 queries when accessing incident properties.
    exports = (
        db.query(Export)
        .options(joinedload(Export.incident))
        .join(Incident, Export.incident_id == Incident.incident_id)
        .filter(Incident.org_id.in_(org_ids))
        .order_by(Export.created_at_utc.desc())
        .all()
    )

    return [
        ExportSummary(
            export_id=e.export_id,
            status=e.status,
            created_at_utc=e.created_at_utc.isoformat() if e.created_at_utc else None,
        )
        for e in exports
    ]


@router.get("/{export_id}")
def get_export_endpoint(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return metadata for a single export.

    Users can only access exports belonging to their organization(s). A
    ``404`` is returned if the export does not exist or is not visible
    to the user.
    """
    export = get_export(db, export_id)
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    # Check visibility: ensure user orgs contain the export's incident org
    org_ids = get_user_org_ids(db, current_user.id)
    incident = db.query(Incident).filter(Incident.incident_id == export.incident_id).first()
    if incident and incident.org_id not in org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

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
    """Return a pre‑signed download URL for a ready export.

    The export must have status ``ready``. Users must belong to the same
    organization as the export's incident. A ``409`` is returned if the
    export is not yet ready, and a ``404`` if it does not exist. The
    function also records an ``EXPORT_DOWNLOADED`` event.
    """
    export = get_export(db, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    # Check visibility
    org_ids = get_user_org_ids(db, current_user.id)
    incident = db.query(Incident).filter(Incident.incident_id == export.incident_id).first()
    if incident and incident.org_id not in org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if export.status != "ready":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export is not ready")

    # Use VaultS3 to generate a presigned URL.
    bucket = export.s3_bucket or settings.S3_BUCKET
    key = export.s3_key or f"exports/{export.export_id}.zip"
    vault = VaultS3(bucket=bucket, region=settings.AWS_REGION)
    presigned_url = vault.presign_download(key)

    # Record download event
    create_event(
        db,
        incident_id=export.incident_id,
        event_type=SystemEventType.EXPORT_DOWNLOADED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload={"export_id": str(export.export_id)},
    )

    return DownloadExportResponse(
        export_id=export.export_id,
        url=presigned_url,
        status="ready",
    )