"""Case operations queue, KPI, alert, and task widget routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.schemas import (
    CaseOpsAlertsResponse,
    CaseOpsBlockerFilter,
    CaseOpsQueueResponse,
    CaseOpsQueueSort,
    CaseOpsSummaryMetricsResponse,
    CaseOpsWorkspaceActivityItem,
    CaseOpsWorkspaceCompleteness,
    CaseOpsWorkspaceCompletenessSection,
    CaseOpsWorkspaceEvidenceSummary,
    CaseOpsWorkspaceNoteItem,
    CaseOpsWorkspaceOwner,
    CaseOpsWorkspaceResponse,
    CaseOpsWorkspaceTaskItem,
    CaseTaskWidgetItem,
    CaseTaskWidgetResponse,
)
from app.case_ops.blockers import detect_blockers
from app.case_ops.completeness import calculate_completeness
from app.case_ops.readiness import derive_readiness_state
from app.case_ops.metrics import (
    query_case_alerts,
    query_incident_queue,
    query_summary_metrics,
)
from app.core.deps import require_workspace_view_permission
from app.db.models import Artifact, AuditEvent, CaseNote, CaseTask, Event, Export, User
from app.db.repo.incidents import get_incident
from app.db.repo.case_tasks import list_my_open_tasks, list_overdue_tasks
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.authz import can_view_incident, require_policy

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
    current_user: User = Depends(require_workspace_view_permission),
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
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    payload = query_summary_metrics(db, org_ids=list(context.org_ids))
    return CaseOpsSummaryMetricsResponse(**payload)


@router.get("/incidents/alerts", response_model=CaseOpsAlertsResponse)
def get_case_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    payload = query_case_alerts(db, org_ids=list(context.org_ids))
    return CaseOpsAlertsResponse(**payload)


@router.get("/tasks/my-open", response_model=CaseTaskWidgetResponse)
def get_my_open_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
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
    current_user: User = Depends(require_workspace_view_permission),
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


@router.get(
    "/incidents/{incident_id}/workspace", response_model=CaseOpsWorkspaceResponse
)
def get_incident_workspace(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, incident_id=incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_view_incident(context, incident))

    artifacts = (
        db.query(Artifact).filter(Artifact.incident_id == incident.incident_id).all()
    )
    exports = db.query(Export).filter(Export.incident_id == incident.incident_id).all()
    events = (
        db.query(Event)
        .filter(Event.incident_id == incident.incident_id)
        .order_by(Event.occurred_at_utc.desc())
        .all()
    )
    audit_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.incident_id == incident.incident_id)
        .order_by(AuditEvent.occurred_at_utc.desc())
        .all()
    )
    open_tasks = (
        db.query(CaseTask)
        .filter(
            CaseTask.incident_id == incident.incident_id,
            CaseTask.status.in_(("open", "in_progress", "blocked")),
        )
        .order_by(CaseTask.due_at_utc.asc().nullslast(), CaseTask.created_at_utc.desc())
        .all()
    )
    recent_notes = (
        db.query(CaseNote)
        .filter(
            CaseNote.incident_id == incident.incident_id,
            or_(CaseNote.is_deleted.is_(False), CaseNote.is_deleted.is_(None)),
        )
        .order_by(CaseNote.created_at_utc.desc())
        .limit(10)
        .all()
    )

    completeness = calculate_completeness(
        artifacts=artifacts, events=events, exports=exports
    )
    blockers = detect_blockers(artifacts=artifacts, events=events, exports=exports)
    readiness = derive_readiness_state(
        case_status=str(incident.case_status),
        completeness_percent=completeness.percent,
        completeness_status=completeness.status,
        blockers=blockers,
    )

    owner = None
    if incident.owner_user_id is not None:
        owner_user = db.query(User).filter(User.id == incident.owner_user_id).first()
        owner = CaseOpsWorkspaceOwner(
            user_id=incident.owner_user_id,
            email=(owner_user.email if owner_user is not None else None),
        )

    activity_entries = [
        CaseOpsWorkspaceActivityItem(
            source="event",
            type=event.event_type,
            occurred_at_utc=event.occurred_at_utc,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            detail=_normalize_detail(event.payload),
        )
        for event in events
    ]
    activity_entries.extend(
        CaseOpsWorkspaceActivityItem(
            source="audit",
            type=audit_event.event_type,
            occurred_at_utc=audit_event.occurred_at_utc,
            actor_type=audit_event.actor_type,
            actor_id=audit_event.actor_id,
            detail=_normalize_detail(audit_event.metadata_json),
        )
        for audit_event in audit_events
    )
    activity_entries.sort(key=lambda entry: entry.occurred_at_utc, reverse=True)

    evidence_status_counts = {
        "captured": sum(1 for artifact in artifacts if artifact.status == "captured"),
        "pending": sum(1 for artifact in artifacts if artifact.status == "pending"),
        "unavailable": sum(
            1 for artifact in artifacts if artifact.status == "unavailable"
        ),
    }

    return CaseOpsWorkspaceResponse(
        incident_id=incident.incident_id,
        owner=owner,
        case_status=incident.case_status,
        readiness_state=readiness.state,
        completeness=CaseOpsWorkspaceCompleteness(
            percent=completeness.percent,
            status=completeness.status,
            missing_items=list(completeness.missing_items),
            sections=[
                CaseOpsWorkspaceCompletenessSection(
                    name=dimension.name,
                    earned=dimension.earned,
                    possible=dimension.possible,
                    percent=dimension.percent,
                    status=dimension.status,
                    missing_items=list(dimension.missing_items),
                )
                for dimension in completeness.dimensions
            ],
        ),
        blockers=[
            {
                "code": blocker.code,
                "severity": blocker.severity,
                "message": blocker.message,
                "blocks_readiness": blocker.blocks_readiness,
                "action_hint": blocker.missing_item.actionHint,
                "missing_item": {
                    "code": blocker.missing_item.code,
                    "category": blocker.missing_item.category,
                    "severity": blocker.missing_item.severity,
                    "message": blocker.missing_item.message,
                    "resolvableBy": blocker.missing_item.resolvableBy,
                    "actionHint": blocker.missing_item.actionHint,
                },
            }
            for blocker in blockers.items
        ],
        evidence_summary=CaseOpsWorkspaceEvidenceSummary(
            total=len(artifacts),
            captured=evidence_status_counts["captured"],
            pending=evidence_status_counts["pending"],
            unavailable=evidence_status_counts["unavailable"],
        ),
        missing_items=list(completeness.missing_items),
        open_tasks=[
            CaseOpsWorkspaceTaskItem(
                task_id=task.task_id,
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_at_utc=task.due_at_utc,
                assigned_to_user_id=task.assigned_to_user_id,
                created_at_utc=task.created_at_utc,
            )
            for task in open_tasks
        ],
        recent_notes=[
            CaseOpsWorkspaceNoteItem(
                note_id=note.note_id,
                body=note.body,
                note_type=str(note.note_type or "standard"),
                tags=list(note.tags_json or []),
                created_by_user_id=note.created_by_user_id,
                created_at_utc=note.created_at_utc,
                edited_at_utc=note.edited_at_utc,
            )
            for note in recent_notes
        ],
        activity=activity_entries,
    )


def _normalize_detail(detail: object) -> dict:
    if detail is None:
        return {}
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, str):
        try:
            loaded = json.loads(detail)
            return loaded if isinstance(loaded, dict) else {"value": loaded}
        except json.JSONDecodeError:
            return {"value": detail}
    return {"value": str(detail)}
