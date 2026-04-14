"""Case operations queue, KPI, alert, and task widget routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    CaseOpsAlertsResponse,
    CaseOpsBlockerFilter,
    CaseOpsQueueResponse,
    CaseOpsQueueSort,
    CaseOpsSummaryMetricsResponse,
    CaseTaskWidgetItem,
    CaseTaskWidgetResponse,
)
from app.case_ops.metrics import query_case_alerts, query_incident_queue, query_summary_metrics
from app.core.deps import get_current_user
from app.db.models import User
from app.db.repo.case_tasks import list_my_open_tasks, list_overdue_tasks
from app.db.session import get_db
from app.security.authn import build_user_auth_context

router = APIRouter()


@router.get("/incidents/queue", response_model=CaseOpsQueueResponse)
def get_incident_queue(
    status: str | None = Query(default=None),
    owner_user_id: uuid.UUID | None = Query(default=None),
    readiness_state: str | None = Query(default=None),
    created_from_utc: datetime | None = Query(default=None),
    created_to_utc: datetime | None = Query(default=None),
    blockers: CaseOpsBlockerFilter | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: CaseOpsQueueSort = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    payload = query_incident_queue(
        db,
        org_ids=list(context.org_ids),
        case_status=status,
        owner_user_id=owner_user_id,
        readiness_state=readiness_state,
        created_from_utc=created_from_utc,
        created_to_utc=created_to_utc,
        blockers=blockers,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return CaseOpsQueueResponse(**payload)


@router.get("/incidents/summary-metrics", response_model=CaseOpsSummaryMetricsResponse)
def get_summary_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    payload = query_summary_metrics(db, org_ids=list(context.org_ids))
    return CaseOpsSummaryMetricsResponse(**payload)


@router.get("/incidents/alerts", response_model=CaseOpsAlertsResponse)
def get_case_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    payload = query_case_alerts(db, org_ids=list(context.org_ids))
    return CaseOpsAlertsResponse(**payload)


@router.get("/tasks/my-open", response_model=CaseTaskWidgetResponse)
def get_my_open_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    tasks = list_my_open_tasks(
        db,
        org_ids=list(context.org_ids),
        user_id=current_user.id,
        now_utc=datetime.now(timezone.utc),
        limit=limit,
    )
    return CaseTaskWidgetResponse(
        items=[
            CaseTaskWidgetItem(
                task_id=task.task_id,
                incident_id=task.incident_id,
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_at_utc=task.due_at_utc,
                assigned_to_user_id=task.assigned_to_user_id,
                created_at_utc=task.created_at_utc,
            )
            for task in tasks
        ]
    )


@router.get("/tasks/overdue", response_model=CaseTaskWidgetResponse)
def get_overdue_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    tasks = list_overdue_tasks(
        db,
        org_ids=list(context.org_ids),
        now_utc=datetime.now(timezone.utc),
        limit=limit,
    )
    return CaseTaskWidgetResponse(
        items=[
            CaseTaskWidgetItem(
                task_id=task.task_id,
                incident_id=task.incident_id,
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_at_utc=task.due_at_utc,
                assigned_to_user_id=task.assigned_to_user_id,
                created_at_utc=task.created_at_utc,
            )
            for task in tasks
        ]
    )
