"""Repository layer for exports."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import Export


def get_exports_by_incident(db: Session, incident_id: _uuid.UUID):
    return db.query(Export).filter(Export.incident_id == incident_id).all()


def get_export(db: Session, export_id: _uuid.UUID):
    return db.query(Export).filter(Export.export_id == export_id).first()


def create_export(
    db: Session,
    incident_id: _uuid.UUID,
    status: str = "requested",
    s3_bucket: str | None = None,
    s3_key: str | None = None,
):
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
