"""Repository layer for artifacts."""

import uuid as _uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Artifact


def get_artifacts_by_incident(db: Session, incident_id: _uuid.UUID):
    return db.query(Artifact).filter(Artifact.incident_id == incident_id).all()


def create_artifact(
    db: Session,
    incident_id: _uuid.UUID,
    artifact_type: str,
    status: str = "pending",
    artifact_id: _uuid.UUID | None = None,
    capture_window_start_utc: datetime | None = None,
    capture_window_end_utc: datetime | None = None,
    s3_bucket: str | None = None,
    s3_key: str | None = None,
    sha256: str | None = None,
    byte_size: int | None = None,
    unavailable_reason_code: str | None = None,
    unavailable_reason_detail: str | None = None,
):
    kwargs = dict(
        incident_id=incident_id,
        artifact_type=artifact_type,
        status=status,
        capture_window_start_utc=capture_window_start_utc,
        capture_window_end_utc=capture_window_end_utc,
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        sha256=sha256,
        byte_size=byte_size,
        unavailable_reason_code=unavailable_reason_code,
        unavailable_reason_detail=unavailable_reason_detail,
    )
    if artifact_id is not None:
        kwargs["artifact_id"] = artifact_id
    artifact = Artifact(**kwargs)
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact
