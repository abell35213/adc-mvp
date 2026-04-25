"""Best-effort audit emission helpers."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
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
    critical: bool = False,
) -> None:
    """Append an audit event when org scope is known.

    By default audit failures are swallowed so a flaky audit pipeline can never
    break a customer-facing request. Pass ``critical=True`` for events whose
    durable persistence is itself a compliance requirement (security/auth
    decisions, role changes, export downloads, etc.); on failure the exception
    is re-raised so the surrounding transaction aborts and the request fails
    closed.
    """
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
        if critical:
            # Compliance-critical events must persist or the request must fail.
            raise


def emit_standard_audit_event(
    db: Session,
    *,
    org_id: uuid.UUID | None,
    actor_type: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    outcome: str | None = None,
    metadata: dict[str, Any] | None = None,
    event_type: str | None = None,
    occurred_at_utc: datetime | None = None,
    critical: bool = False,
) -> None:
    """Emit an audit event with standardized actor/org/entity/action metadata."""
    timestamp = occurred_at_utc or datetime.now(timezone.utc)
    emit_audit_event(
        db,
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        event_type=event_type or action,
        outcome=outcome,
        metadata={
            "schema_version": "audit.v1",
            "actor": {"type": actor_type, "id": actor_id},
            "org": {"id": str(org_id) if org_id else None},
            "entity": {"type": entity_type, "id": entity_id},
            "action": action,
            "timestamp": timestamp.isoformat(),
            **(metadata or {}),
        },
        critical=critical,
    )
