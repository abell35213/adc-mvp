"""Backward-compatible notification task aliases."""

import logging

from app.tasks.celery_app import celery_app
from app.tasks.notification_tasks import notify_safety_manager

logger = logging.getLogger(__name__)


@celery_app.task
def notify_safety(incident_id: str):
    """Backward-compatible alias for legacy task name."""
    logger.warning(
        "notify_safety is deprecated; forwarding incident %s to notify_safety_manager",
        incident_id,
    )
    return notify_safety_manager(incident_id)
