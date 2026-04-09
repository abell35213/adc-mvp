"""Best-effort audit emission helpers."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit.models import AuditEventCreate
from app.audit.service import append_event
from app.observability.detection import audit_activity_detector
from app.observability.redaction import redact_log_data

logger = logging.getLogger(__name__)


def emit_audit_event(
    db: Session,
    *,
    org_id: uuid.UUID | None,
    actor_type: str,
    actor_id: str,
    action: str,
    event_type: str,
    outcome: str | None = None,
    incident_id: uuid.UUID | None = None,
    export_id: uuid.UUID | None = None,
    artifact_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append an audit event when org scope is known; swallow audit failures."""
    if org_id is None:
        return
    try:
        append_event(
            db,
            AuditEventCreate(
                org_id=org_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                event_type=event_type,
                outcome=outcome,
                incident_id=incident_id,
                export_id=export_id,
                artifact_id=artifact_id,
                metadata=metadata or {},
            ),
        )
        alerts = audit_activity_detector.evaluate(
            org_id=str(org_id),
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            event_type=event_type,
            outcome=outcome,
            metadata=metadata or {},
        )
        for alert in alerts:
            logger.warning(
                alert.message,
                extra=redact_log_data(
                    {
                        "alert": alert.rule,
                        "severity": alert.severity,
                        **alert.context,
                    }
                ),
            )
    except Exception:
        logger.exception(
            "Failed to append audit event",
            extra=redact_log_data({
                "org_id": str(org_id),
                "actor_type": actor_type,
                "actor_id": actor_id,
                "action": action,
                "event_type": event_type,
                "metadata": metadata or {},
            }),
        )
