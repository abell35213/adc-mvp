"""Export generation tasks."""

from app.tasks.celery_app import celery_app


@celery_app.task
def generate_export(incident_id: int, format: str = "pdf"):
    """Generate an export package for an incident."""
    # Placeholder: build and store the export
    return {"incident_id": incident_id, "format": format, "status": "generated"}
