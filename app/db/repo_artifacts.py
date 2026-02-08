"""Repository layer for artifacts."""

from sqlalchemy.orm import Session

from app.db.models import Artifact


def get_artifacts_by_incident(db: Session, incident_id: int):
    return db.query(Artifact).filter(Artifact.incident_id == incident_id).all()


def create_artifact(db: Session, incident_id: int, artifact_type: str, storage_path: str):
    artifact = Artifact(
        incident_id=incident_id, artifact_type=artifact_type, storage_path=storage_path
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact
