"""Driver artifact upload/list routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import (
    ArtifactSummary,
    DriverArtifactCompleteRequest,
    DriverArtifactCompleteResponse,
    DriverArtifactListResponse,
    DriverArtifactUploadUrlRequest,
    DriverArtifactUploadUrlResponse,
)
from app.core.deps import get_current_driver
from app.db.models import Driver
from app.db.session import get_db
from app.services.artifact_upload_service import (
    complete_driver_artifact_upload,
    issue_driver_artifact_upload_url,
    list_driver_artifacts,
)

router = APIRouter()


@router.post(
    "/incidents/{incident_id}/artifacts/upload-url",
    response_model=DriverArtifactUploadUrlResponse,
)
def create_driver_artifact_upload_url(
    incident_id: uuid.UUID,
    body: DriverArtifactUploadUrlRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    artifact, upload_url, expires_in = issue_driver_artifact_upload_url(
        db,
        incident_id=incident_id,
        driver=driver,
        artifact_type=body.artifact_type,
        content_type=body.content_type,
        file_name=body.file_name,
    )
    return DriverArtifactUploadUrlResponse(
        artifact_id=artifact.artifact_id,
        upload_url=upload_url,
        s3_key=artifact.s3_key or "",
        expires_in_seconds=expires_in,
        content_type=body.content_type,
    )


@router.post(
    "/incidents/{incident_id}/artifacts/complete",
    response_model=DriverArtifactCompleteResponse,
)
def complete_driver_artifact(
    incident_id: uuid.UUID,
    body: DriverArtifactCompleteRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    artifact = complete_driver_artifact_upload(
        db,
        incident_id=incident_id,
        driver=driver,
        artifact_id=body.artifact_id,
        byte_size=body.byte_size,
        sha256=body.sha256,
    )
    return DriverArtifactCompleteResponse(
        artifact_id=artifact.artifact_id,
        status=artifact.status,
    )


@router.get(
    "/incidents/{incident_id}/artifacts",
    response_model=DriverArtifactListResponse,
)
def get_driver_artifacts(
    incident_id: uuid.UUID,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    artifacts = list_driver_artifacts(
        db,
        incident_id=incident_id,
        driver=driver,
    )
    return DriverArtifactListResponse(
        artifacts=[
            ArtifactSummary(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                status=artifact.status,
                captured_at_utc=artifact.capture_window_end_utc,
                unavailable_reason=artifact.unavailable_reason_code,
            )
            for artifact in artifacts
        ]
    )
