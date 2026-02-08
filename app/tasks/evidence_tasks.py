"""Evidence collection tasks."""

from app.tasks.celery_app import celery_app


@celery_app.task
def collect_evidence(incident_id: str):
    """Collect all evidence artifacts for an incident."""
    # Placeholder: orchestrate evidence collection
    return {"incident_id": incident_id, "status": "collected"}
