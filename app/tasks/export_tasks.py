"""Export generation tasks."""

from app.tasks.celery_app import celery_app


@celery_app.task
def generate_export(export_id: str, incident_id: str, format: str = "zip"):
    """Generate an export package for an incident."""
    # Placeholder: build ZIP, upload to S3, set status to ready
    return {
        "export_id": export_id,
        "incident_id": incident_id,
        "format": format,
        "status": "ready",
    }
