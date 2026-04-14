"""Repository helpers for case task dashboard queries."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import CaseTask

OPEN_TASK_STATUSES: tuple[str, ...] = ("open", "in_progress", "blocked")


def list_my_open_tasks(
    db: Session,
    *,
    org_ids: list[_uuid.UUID],
    user_id: _uuid.UUID,
    now_utc: datetime,
    limit: int = 20,
) -> list[CaseTask]:
    if not org_ids:
        return []
    return (
        db.query(CaseTask)
        .filter(
            CaseTask.org_id.in_(org_ids),
            CaseTask.assigned_to_user_id == user_id,
            CaseTask.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(CaseTask.due_at_utc.asc().nullslast(), CaseTask.created_at_utc.desc())
        .limit(limit)
        .all()
    )


def list_overdue_tasks(
    db: Session,
    *,
    org_ids: list[_uuid.UUID],
    now_utc: datetime,
    limit: int = 20,
) -> list[CaseTask]:
    if not org_ids:
        return []
    return (
        db.query(CaseTask)
        .filter(
            CaseTask.org_id.in_(org_ids),
            CaseTask.status.in_(OPEN_TASK_STATUSES),
            CaseTask.due_at_utc.is_not(None),
            CaseTask.due_at_utc < now_utc,
        )
        .order_by(CaseTask.due_at_utc.asc(), CaseTask.created_at_utc.desc())
        .limit(limit)
        .all()
    )


def count_overdue_tasks(
    db: Session,
    *,
    org_ids: list[_uuid.UUID],
    now_utc: datetime,
) -> int:
    if not org_ids:
        return 0
    return (
        db.query(CaseTask)
        .filter(
            CaseTask.org_id.in_(org_ids),
            CaseTask.status.in_(OPEN_TASK_STATUSES),
            CaseTask.due_at_utc.is_not(None),
            CaseTask.due_at_utc < now_utc,
        )
        .count()
    )
