"""Celery tasks for TMS sync (Phase 2).

* :func:`sync_tms_org` — pulls every active TMS connection for one org. Run
  on the per-connection ``schedule_cron`` (via Celery beat) **and**
  on-demand from the Org Settings UI / when an incident is opened to top up
  the local cache before a potential crash packet build.
* :func:`sync_tms_connection` — single-connection variant for the manual
  "Sync now" button.

Both tasks are best-effort: failures surface via
:attr:`TmsConnection.status` / :attr:`TmsConnection.last_error` rather than
blocking the packet-dispatch path (per the plan: "Packet has a hard
15-minute SLA — we must not depend on third-party DB latency").
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
    name="app.tasks.tms_sync_tasks.sync_tms_org",
    acks_late=True,
    soft_time_limit=300,
    time_limit=360,
)
def sync_tms_org(org_id: str):
    """Sync every active TMS connection for ``org_id``."""
    from app.services.tms_sync_service import sync_org

    db = _get_db()
    try:
        results = sync_org(db, org_id=_uuid.UUID(org_id))
        return {
            "org_id": org_id,
            "connection_count": len(results),
            "total_inserted": sum(r.total_inserted for r in results),
            "total_updated": sum(r.total_updated for r in results),
            "errors": [r.error for r in results if r.error],
        }
    except Exception:
        increment(MetricNames.CELERY_TASK_FAILURES)
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.tms_sync_tasks.sync_tms_connection",
    acks_late=True,
    soft_time_limit=300,
    time_limit=360,
)
def sync_tms_connection(tms_connection_id: str):
    """Sync exactly one TMS connection (the "Sync now" button)."""
    from app.services.tms_sync_service import sync_connection

    db = _get_db()
    try:
        result = sync_connection(
            db, tms_connection_id=_uuid.UUID(tms_connection_id)
        )
        return {
            "tms_connection_id": tms_connection_id,
            "total_inserted": result.total_inserted,
            "total_updated": result.total_updated,
            "error": result.error,
        }
    except Exception:
        increment(MetricNames.CELERY_TASK_FAILURES)
        raise
    finally:
        db.close()
