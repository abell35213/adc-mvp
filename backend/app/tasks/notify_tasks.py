"""Notification tasks for safety alerts."""

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def notify_safety(incident_id: str):
    """Notify safety team that an incident was initiated."""
    logger.info("Safety notification queued for incident %s", incident_id)
    return {"incident_id": incident_id, "status": "notified"}
