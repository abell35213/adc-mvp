"""Periodic re-poll tasks for FMCSA MCMIS snapshots.

Two triggers:

* :func:`refresh_open_incident_inspections_periodic` — daily refresh
  for non-closed incidents whose snapshot is stale.
* :func:`refresh_carrier_inspections_periodic` — nightly per-org
  refresh so future incidents hit a warm cache.

Both gated by ``settings.FMCSA_INSPECTIONS_REPOLL_ENABLED`` and
rate-limited per-org via :func:`enforce_rate_limit`.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.models import Incident, IntegrationOperation, Org
from app.db.repo.fmcsa_inspections import (
    get_latest_succeeded_snapshot,
    is_snapshot_fresh,
    mark_snapshots_stale,
)
from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app
from app.tasks.evidence_tasks import capture_driver_violation_history

logger = logging.getLogger(__name__)


def _get_db():
    return SessionLocal()


@celery_app.task(name="app.tasks.fmcsa_repoll_tasks.refresh_open_incident_inspections_periodic")
def refresh_open_incident_inspections_periodic() -> dict:
    """For each open incident with a stale snapshot, mark stale + re-enqueue."""
    if not getattr(settings, "FMCSA_INSPECTIONS_REPOLL_ENABLED", True):
        return {"status": "disabled"}

    refresh_hours = int(
        getattr(settings, "FMCSA_INCIDENT_REFRESH_INTERVAL_HOURS", 24)
    )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=refresh_hours)

    db = _get_db()
    requeued = 0
    try:
        incidents = (
            db.query(Incident)
            .filter(
                Incident.case_status.notin_(("closed", "exported")),
                Incident.adc_driver_id.isnot(None),
            )
            .all()
        )
        for incident in incidents:
            if incident.org_id is None:
                continue
            org = db.query(Org).filter(Org.id == incident.org_id).first()
            if org is None or not (org.usdot_number or "").strip():
                continue
            snapshot = get_latest_succeeded_snapshot(db, org_id=incident.org_id)
            if snapshot is not None and is_snapshot_fresh(
                snapshot, ttl_hours=refresh_hours, now=cutoff
            ):
                continue
            mark_snapshots_stale(db, org_id=incident.org_id)
            # Find the most recent inspections operation for this incident
            # so we can rerun via the same operation id (best-effort).
            op = (
                db.query(IntegrationOperation)
                .filter(
                    IntegrationOperation.incident_id == incident.incident_id,
                    IntegrationOperation.domain == "inspections",
                )
                .order_by(IntegrationOperation.created_at_utc.desc())
                .first()
            )
            if op is None:
                continue
            capture_driver_violation_history.delay(
                operation_id=str(op.operation_id),
                evidence_request_id=str(op.operation_id),
                org_id=str(incident.org_id),
                incident_id=str(incident.incident_id),
                adc_driver_id=incident.adc_driver_id,
                usdot_number=org.usdot_number.strip(),
            )
            requeued += 1
    finally:
        db.close()
    return {"status": "ok", "requeued": requeued}


@celery_app.task(name="app.tasks.fmcsa_repoll_tasks.refresh_carrier_inspections_periodic")
def refresh_carrier_inspections_periodic() -> dict:
    """Refresh the snapshot for every org with a USDOT (warms the cache)."""
    if not getattr(settings, "FMCSA_INSPECTIONS_REPOLL_ENABLED", True):
        return {"status": "disabled"}

    db = _get_db()
    refreshed = 0
    try:
        orgs = (
            db.query(Org)
            .filter(Org.usdot_number.isnot(None))
            .all()
        )
        for org in orgs:
            usdot = (org.usdot_number or "").strip()
            if not usdot:
                continue
            mark_snapshots_stale(db, org_id=org.id)
            # Use a deterministic synthetic operation id so this task is
            # idempotent across runs (best-effort: the worker treats a
            # missing operation as a no-op).
            synthetic_op = str(_uuid.uuid4())
            capture_driver_violation_history.delay(
                operation_id=synthetic_op,
                evidence_request_id=synthetic_op,
                org_id=str(org.id),
                incident_id=str(_uuid.UUID(int=0)),
                adc_driver_id=None,
                usdot_number=usdot,
            )
            refreshed += 1
    finally:
        db.close()
    return {"status": "ok", "refreshed": refreshed}
