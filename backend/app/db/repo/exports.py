"""Repository layer for exports."""

import uuid as _uuid
from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import Export, Incident


def _get_export_query(db: Session, export_id: _uuid.UUID):
    """Helper to get base query for a single export."""
    return db.query(Export).filter(Export.export_id == export_id)


def get_exports_by_incident(db: Session, incident_id: _uuid.UUID) -> list[Export]:
    """Retrieve all exports for a specific incident."""
    return db.query(Export).filter(Export.incident_id == incident_id).all()


def list_exports_for_org_ids(db: Session, org_ids: list[_uuid.UUID]) -> list[Export]:
    """List exports visible to the caller's organizations, newest first."""
    if not org_ids:
        return []

    return (
        db.query(Export)
        .outerjoin(Incident, Incident.incident_id == Export.incident_id)
        .filter(
            or_(
                Export.org_id.in_(org_ids),
                and_(Export.org_id.is_(None), Incident.org_id.in_(org_ids)),
            )
        )
        .order_by(Export.created_at_utc.desc())
        .all()
    )


def get_export(db: Session, export_id: _uuid.UUID) -> Optional[Export]:
    """Retrieve a single export by ID."""
    return _get_export_query(db, export_id).first()


def create_export(
    db: Session,
    incident_id: _uuid.UUID,
    org_id: Optional[_uuid.UUID] = None,
    status: str = "requested",
    export_type: str = "court_defense",
    requested_by_user_id: Optional[_uuid.UUID] = None,
    options_json: Optional[dict[str, Any]] = None,
    progress_stage: str = "request_accepted",
    s3_bucket: Optional[str] = None,
    s3_key: Optional[str] = None,
) -> Export:
    """Create a new export record."""
    export = Export(
        org_id=org_id,
        incident_id=incident_id,
        export_type=export_type,
        requested_by_user_id=requested_by_user_id,
        options_json=options_json or {},
        status=status,
        progress_stage=progress_stage,
        s3_bucket=s3_bucket,
        s3_key=s3_key,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def update_export(
    db: Session,
    export_id: _uuid.UUID,
    status: Optional[str] = None,
    progress_stage: Optional[str] = None,
    error_message: Optional[str] = None,
    options_json: Optional[dict[str, Any]] = None,
    package_sha256: Optional[str] = None,
    byte_size: Optional[int] = None,
    artifact_count: Optional[int] = None,
    timeline_event_count: Optional[int] = None,
    s3_bucket: Optional[str] = None,
    s3_key: Optional[str] = None,
) -> Optional[Export]:
    """Update an existing export record."""
    export = _get_export_query(db, export_id).with_for_update().first()

    if export is None:
        return None

    # Only update fields that are provided
    if status is not None:
        export.status = status
    if progress_stage is not None:
        export.progress_stage = progress_stage
    if error_message is not None:
        export.error_message = error_message
    if options_json is not None:
        export.options_json = options_json
    if package_sha256 is not None:
        export.package_sha256 = package_sha256
    if byte_size is not None:
        export.byte_size = byte_size
    if artifact_count is not None:
        export.artifact_count = artifact_count
    if timeline_event_count is not None:
        export.timeline_event_count = timeline_event_count
    if s3_bucket is not None:
        export.s3_bucket = s3_bucket
    if s3_key is not None:
        export.s3_key = s3_key

    db.commit()
    db.refresh(export)
    return export
