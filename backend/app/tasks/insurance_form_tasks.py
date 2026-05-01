"""Celery tasks for insurance form filling (Phase 3).

* :func:`fill_insurance_form` — orchestrates a single (incident, template)
  fill. Idempotent on ``(incident_id, template_id, payload_hash)``: re-runs
  with unchanged canonical data return the existing filling.

The task runs on the ``evidence`` queue alongside the other artifact-
producing work.
"""

from __future__ import annotations

import logging
import uuid as _uuid

from app.core.metrics import MetricNames, increment
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    from app.db.session import SessionLocal

    return SessionLocal()


@celery_app.task(
    name="app.tasks.insurance_form_tasks.fill_insurance_form",
    acks_late=True,
    soft_time_limit=120,
    time_limit=180,
)
def fill_insurance_form(incident_id: str, template_id: str):
    from app.services.insurance_form_fill_service import fill_form_for_incident

    db = _get_db()
    try:
        result = fill_form_for_incident(
            db,
            incident_id=_uuid.UUID(incident_id),
            template_id=_uuid.UUID(template_id),
        )
        return {
            "filling_id": str(result.filling.id),
            "status": result.filling.status,
            "created": result.created,
            "missing_required_fields": list(
                result.filling.missing_required_fields or []
            ),
        }
    except Exception:
        increment(MetricNames.CELERY_TASK_FAILURES)
        raise
    finally:
        db.close()
