"""Service logic for incident ownership assignment workflows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Incident, UserOrg


def patch_incident_owner(
    *,
    db: Session,
    incident: Incident,
    org_ids: list[uuid.UUID],
    actor_user_id: uuid.UUID,
    operation: str,
    owner_user_id: uuid.UUID | None,
) -> Incident:
    """Apply owner assign/reassign/clear operation and mutate queue metadata."""
    now = datetime.now(timezone.utc)

    if operation in {"assign", "reassign"}:
        assert owner_user_id is not None
        is_user_in_org = (
            db.query(UserOrg)
            .filter(UserOrg.user_id == owner_user_id, UserOrg.org_id.in_(org_ids))
            .first()
            is not None
        )
        if not is_user_in_org:
            raise HTTPException(status_code=404, detail="Owner user not found")

        incident.owner_user_id = owner_user_id
        incident.owner_assigned_at_utc = now
        incident.owner_assigned_by_user_id = actor_user_id
    else:
        incident.owner_user_id = None
        incident.owner_assigned_at_utc = None
        incident.owner_assigned_by_user_id = None
        incident.team_queue = "Unassigned"

    incident.last_activity_at_utc = now
    db.flush()
    return incident
