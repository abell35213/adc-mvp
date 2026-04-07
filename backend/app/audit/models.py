"""Audit event domain models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AuditEventCreate:
    """Input payload for writing an immutable audit event."""

    org_id: uuid.UUID
    actor_type: str
    actor_id: str
    action: str
    event_type: str
    outcome: str | None = None
    incident_id: uuid.UUID | None = None
    export_id: uuid.UUID | None = None
    artifact_id: uuid.UUID | None = None
    metadata: dict[str, Any] | None = None
    occurred_at_utc: datetime | None = None


@dataclass(slots=True)
class AuditEventRetentionUpdate:
    """Controlled retention-only fields that can be updated later."""

    retention_expires_at_utc: datetime | None = None
    retention_purged_at_utc: datetime | None = None
