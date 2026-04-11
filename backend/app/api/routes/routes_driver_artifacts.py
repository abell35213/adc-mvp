"""Driver artifact upload/list routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    ArtifactSummary,
    DriverArtifactCompleteRequest,
    DriverArtifactCompleteResponse,
    DriverArtifactListResponse,
    DriverArtifactUploadUrlRequest,
    DriverArtifactUploadUrlResponse,
)
from app.audit.emitter import emit_audit_event
from app.core.deps import get_current_driver
from app.db.models import Driver
from app.db.session import get_db
from app.services.artifact_upload_service import (
    complete_driver_artifact_upload,
    issue_driver_artifact_upload_url,
    list_driver_artifacts,
)
from app.services.rate_limit_service import enforce_rate_limit
from app.core.config import settings
from app.services.dashcam_reason_codes import dashcam_reason_message

router = APIRouter()


@router.post(
    "/incidents/{incident_id}/artifacts/upload-url",
    response_model=DriverArtifactUploadUrlResponse,
)
def create_driver_artifact_upload_url(
    incident_id: uuid.UUID,
    body: DriverArtifactUploadUrlRequest,
    request: Request,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(
        request,
        bucket_name="driver_upload_url",
        subject=str(driver.driver_id),
        max_calls=settings.DRIVER_UPLOAD_URL_RATE_LIMIT,
        window_seconds=settings.DRIVER_UPLOAD_URL_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many upload URL requests. Please retry later.",
    )
    artifact, upload_url, expires_in = issue_driver_artifact_upload_url(
        db,
        incident_id=incident_id,
        driver=driver,
        artifact_type=body.artifact_type,
        content_type=body.content_type,
        file_name=body.file_name,
    )
    emit_audit_event(
        db,
        org_id=driver.org_id,
        actor_type="driver",
        actor_id=str(driver.driver_id),
        action="artifact.upload_url.request",
        event_type="artifact_retrieved",
        outcome="success",
        incident_id=incident_id,
        artifact_id=artifact.artifact_id,
        metadata={"artifact_type": artifact.artifact_type},
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
    emit_audit_event(
        db,
        org_id=driver.org_id,
        actor_type="driver",
        actor_id=str(driver.driver_id),
        action="artifact.upload.complete",
        event_type="artifact_retrieved",
        outcome="success",
        incident_id=incident_id,
        artifact_id=artifact.artifact_id,
        metadata={"byte_size": body.byte_size},
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
    for artifact in artifacts:
        emit_audit_event(
            db,
            org_id=driver.org_id,
            actor_type="driver",
            actor_id=str(driver.driver_id),
            action="artifact.retrieve",
            event_type="artifact_retrieved",
            outcome="success",
            incident_id=incident_id,
            artifact_id=artifact.artifact_id,
            metadata={"artifact_type": artifact.artifact_type, "status": artifact.status},
        )
    return DriverArtifactListResponse(
        artifacts=[
            ArtifactSummary(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                status=artifact.status,
                captured_at_utc=artifact.capture_window_end_utc,
                unavailable_reason=(
                    dashcam_reason_message(artifact.unavailable_reason_code)
                    if (artifact.artifact_type or "").startswith("dash_cam_video")
                    else artifact.unavailable_reason_code
                ),
            )
            for artifact in artifacts
        ]
    )
