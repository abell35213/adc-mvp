"""Repository layer for exports."""

from sqlalchemy.orm import Session

from app.db.models import Export


def get_exports_by_incident(db: Session, incident_id: int):
    return db.query(Export).filter(Export.incident_id == incident_id).all()


def create_export(db: Session, incident_id: int, format: str, storage_path: str | None = None):
    export = Export(incident_id=incident_id, format=format, storage_path=storage_path)
    db.add(export)
    db.commit()
    db.refresh(export)
    return export
