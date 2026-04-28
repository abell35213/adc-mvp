"""Service logic for driver-managed artifact upload flow."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Artifact, Driver, Incident
from app.domain.state_transitions import validate_incident_transition

UPLOAD_URL_EXPIRATION_SECONDS = 300
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "video/mp4",
}
ALLOWED_ARTIFACT_CONTENT_TYPES = {
    "driver_photo": {"image/jpeg", "image/png"},
    "driver_document": {"application/pdf", "image/jpeg", "image/png"},
    "driver_video": {"video/mp4"},
}


def _validate_incident_driver_ownership(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
) -> Incident:
    incident = (
        db.query(Incident)
        .filter(
            Incident.incident_id == incident_id,
            Incident.org_id == driver.org_id,
            Incident.adc_driver_id == str(driver.driver_id),
        )
        .first()
    )
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident


def _file_extension(file_name: str) -> str:
    base_name = os.path.basename(file_name)
    match = re.search(r"\.([A-Za-z0-9]{1,8})$", base_name)
    if not match:
        return "bin"
    return match.group(1).lower()


def issue_driver_artifact_upload_url(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
    artifact_type: str,
    content_type: str,
    file_name: str,
) -> tuple[Artifact, str, int]:
    incident = _validate_incident_driver_ownership(
        db,
        incident_id=incident_id,
        driver=driver,
    )

    validate_incident_transition(current_status=incident.status, next_status="evidence_capturing", actor="driver_api")

    normalized_artifact_type = artifact_type.strip().lower()
    if normalized_artifact_type not in ALLOWED_ARTIFACT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unsupported artifact type",
        )

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unsupported content type",
        )

    allowed_for_type = ALLOWED_ARTIFACT_CONTENT_TYPES[normalized_artifact_type]
    if content_type not in allowed_for_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Content type is not allowed for artifact type",
        )

    artifact = Artifact(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        artifact_type=normalized_artifact_type,
        status="pending",
        capture_window_end_utc=datetime.now(timezone.utc),
    )
    ext = _file_extension(file_name)
    artifact.s3_bucket = settings.S3_ARTIFACTS_BUCKET
    artifact.s3_key = (
        f"org/{incident.org_id}/incidents/{incident.incident_id}/"
        f"driver/{normalized_artifact_type}/{artifact.artifact_id}.{ext}"
    )

    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": artifact.s3_bucket,
            "Key": artifact.s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=UPLOAD_URL_EXPIRATION_SECONDS,
    )

    return artifact, upload_url, UPLOAD_URL_EXPIRATION_SECONDS


def complete_driver_artifact_upload(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
    artifact_id: uuid.UUID,
    byte_size: int,
    sha256: str | None,
) -> Artifact:
    incident = _validate_incident_driver_ownership(
        db,
        incident_id=incident_id,
        driver=driver,
    )

    artifact = (
        db.query(Artifact)
        .filter(
            Artifact.artifact_id == artifact_id,
            Artifact.incident_id == incident_id,
            Artifact.org_id == incident.org_id,
        )
        .first()
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    if artifact.status == "captured":
        return artifact

    if artifact.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Artifact is not completable from status={artifact.status}",
        )

    artifact.status = "captured"
    artifact.byte_size = byte_size
    artifact.sha256 = sha256
    artifact.uploaded_at_utc = datetime.now(timezone.utc)
    db.commit()
    db.refresh(artifact)
    return artifact


def list_driver_artifacts(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
) -> list[Artifact]:
    _validate_incident_driver_ownership(db, incident_id=incident_id, driver=driver)
    return (
        db.query(Artifact)
        .filter(Artifact.incident_id == incident_id)
        .order_by(Artifact.created_at_utc.asc())
        .all()
    )
