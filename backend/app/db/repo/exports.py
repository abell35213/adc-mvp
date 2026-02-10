"""Repository layer for exports."""

import uuid as _uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Export


def _get_export_query(db: Session, export_id: _uuid.UUID):
    """Helper to get base query for a single export."""
    return db.query(Export).filter(Export.export_id == export_id)


def get_exports_by_incident(db: Session, incident_id: _uuid.UUID) -> list[Export]:
    """Retrieve all exports for a specific incident."""
    return db.query(Export).filter(Export.incident_id == incident_id).all()


def get_export(db: Session, export_id: _uuid.UUID) -> Optional[Export]:
    """Retrieve a single export by ID."""
    return _get_export_query(db, export_id).first()


def create_export(
    db: Session,
    incident_id: _uuid.UUID,
    status: str = "requested",
    s3_bucket: Optional[str] = None,
    s3_key: Optional[str] = None,
) -> Export:
    """Create a new export record."""
    export = Export(
        incident_id=incident_id,
        status=status,
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
    if s3_bucket is not None:
        export.s3_bucket = s3_bucket
    if s3_key is not None:
        export.s3_key = s3_key

    db.commit()
    db.refresh(export)
    return export
