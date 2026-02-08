"""Evidence collection tasks."""

from app.tasks.celery_app import celery_app


@celery_app.task
def capture_dashcam(incident_id: str):
    """Capture dashcam footage for an incident."""
    # Placeholder: fetch dashcam video from provider
    return {"incident_id": incident_id, "type": "dashcam", "status": "captured"}


@celery_app.task
def capture_telematics(incident_id: str):
    """Capture telematics bundle for an incident."""
    # Placeholder: fetch telematics data from Samsara
    return {"incident_id": incident_id, "type": "telematics", "status": "captured"}


@celery_app.task
def collect_evidence(incident_id: str):
    """Collect all evidence artifacts for an incident."""
    # Placeholder: orchestrate evidence collection
    return {"incident_id": incident_id, "status": "collected"}
