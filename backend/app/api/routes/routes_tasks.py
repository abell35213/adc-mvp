"""Incident task CRUD and workflow routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.schemas import (
    IncidentTaskCancelRequest,
    IncidentTaskCreateRequest,
    IncidentTaskItem,
    IncidentTaskListResponse,
    IncidentTaskPatchRequest,
)
from app.audit.emitter import emit_audit_event
from app.core.deps import require_task_operations_permission, require_workspace_view_permission
from app.db.models import CaseTask, Incident, User
from app.db.repo.events import create_event
from app.db.repo.incidents import get_incident
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.security.authn import build_user_auth_context
from app.security.authz import can_modify_incident, can_view_incident, require_policy

router = APIRouter()


@router.get("/incidents/{incident_id}/tasks", response_model=IncidentTaskListResponse)
def list_incident_tasks(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    incident, _ = _require_incident_access(
        db=db,
        current_user=current_user,
        incident_id=incident_id,
        write_access=False,
    )
    now_utc = datetime.now(timezone.utc)
    tasks = (
        db.query(CaseTask)
        .filter(CaseTask.incident_id == incident.incident_id)
        .order_by(CaseTask.due_at_utc.asc().nullslast(), CaseTask.created_at_utc.desc())
        .all()
    )
    return IncidentTaskListResponse(items=[_to_task_item(task, now_utc=now_utc) for task in tasks])


@router.post("/incidents/{incident_id}/tasks", response_model=IncidentTaskItem)
def create_incident_task(
    incident_id: uuid.UUID,
    request: IncidentTaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_task_operations_permission),
):
    incident, _ = _require_incident_access(
        db=db,
        current_user=current_user,
        incident_id=incident_id,
        write_access=True,
    )

    now_utc = datetime.now(timezone.utc)
    task = CaseTask(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        title=request.title,
        description=request.description,
        task_type=request.task_type,
        priority=request.priority,
        due_at_utc=request.due_at_utc,
        assigned_to_user_id=request.assigned_to_user_id,
        created_by_user_id=current_user.id,
    )
    if request.assigned_to_user_id is not None:
        task.assigned_at_utc = now_utc
        task.assigned_by_user_id = current_user.id

    db.add(task)
    db.commit()
    db.refresh(task)

    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="task.create",
        event_type="incident_task_created",
        outcome="success",
        incident_id=incident.incident_id,
        metadata={"task_id": str(task.task_id), "task_type": task.task_type, "priority": task.priority},
    )
    event_payload = _event_payload(
        actor_id=current_user.id,
        incident_id=incident.incident_id,
        org_id=incident.org_id,
        task_id=task.task_id,
        reason=None,
        previous={"status": None, "assigned_to_user_id": None},
        new={"status": _api_status(task.status), "assigned_to_user_id": str(task.assigned_to_user_id) if task.assigned_to_user_id else None},
    )
    create_event(
        db,
        incident_id=incident.incident_id,
        event_type=SystemEventType.INCIDENT_TASK_CREATED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=event_payload,
    )

    return _to_task_item(task, now_utc=now_utc)


@router.patch("/tasks/{task_id}", response_model=IncidentTaskItem)
def patch_task(
    task_id: uuid.UUID,
    request: IncidentTaskPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_task_operations_permission),
):
    task, incident = _require_task_write_access(db=db, current_user=current_user, task_id=task_id)
    now_utc = datetime.now(timezone.utc)

    previous_assignee = task.assigned_to_user_id
    previous_status = _api_status(task.status)

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.priority is not None:
        task.priority = request.priority
    if request.task_type is not None:
        task.task_type = request.task_type
    if request.due_at_utc is not None:
        task.due_at_utc = request.due_at_utc

    if request.assigned_to_user_id is not None and request.assigned_to_user_id != task.assigned_to_user_id:
        task.assigned_to_user_id = request.assigned_to_user_id
        task.assigned_at_utc = now_utc
        task.assigned_by_user_id = current_user.id

    if request.status is not None:
        _validate_transition(current_status=_api_status(task.status), next_status=request.status)
        _apply_status(task=task, next_status=request.status, actor_user_id=current_user.id, now_utc=now_utc)

    db.add(task)
    db.commit()
    db.refresh(task)

    if previous_assignee != task.assigned_to_user_id:
        event_payload = _event_payload(
            actor_id=current_user.id,
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            task_id=task.task_id,
            reason="reassign",
            previous={"assigned_to_user_id": str(previous_assignee) if previous_assignee else None},
            new={"assigned_to_user_id": str(task.assigned_to_user_id) if task.assigned_to_user_id else None},
        )
        emit_audit_event(
            db,
            org_id=incident.org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="task.reassign",
            event_type="incident_task_reassigned",
            outcome="success",
            incident_id=incident.incident_id,
            metadata={
                **event_payload,
                "task_id": str(task.task_id),
                "previous_assignee": str(previous_assignee) if previous_assignee else None,
                "new_assignee": str(task.assigned_to_user_id) if task.assigned_to_user_id else None,
            },
        )
        create_event(
            db,
            incident_id=incident.incident_id,
            event_type=SystemEventType.INCIDENT_TASK_REASSIGNED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload=event_payload,
        )

    if previous_status != _api_status(task.status):
        emit_audit_event(
            db,
            org_id=incident.org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="task.status.patch",
            event_type="incident_task_status_updated",
            outcome="success",
            incident_id=incident.incident_id,
            metadata={"task_id": str(task.task_id), "from": previous_status, "to": _api_status(task.status)},
        )

    return _to_task_item(task, now_utc=now_utc)


@router.post("/tasks/{task_id}/complete", response_model=IncidentTaskItem)
def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_task_operations_permission),
):
    task, incident = _require_task_write_access(db=db, current_user=current_user, task_id=task_id)
    now_utc = datetime.now(timezone.utc)
    _validate_transition(current_status=_api_status(task.status), next_status="completed")
    _apply_status(task=task, next_status="completed", actor_user_id=current_user.id, now_utc=now_utc)
    db.add(task)
    db.commit()
    db.refresh(task)

    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="task.complete",
        event_type="incident_task_completed",
        outcome="success",
        incident_id=incident.incident_id,
        metadata={"task_id": str(task.task_id)},
    )
    create_event(
        db,
        incident_id=incident.incident_id,
        event_type=SystemEventType.INCIDENT_TASK_COMPLETED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=_event_payload(
            actor_id=current_user.id,
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            task_id=task.task_id,
            reason=None,
            previous={"status": "open"},
            new={"status": "completed"},
        ),
    )

    return _to_task_item(task, now_utc=now_utc)


@router.post("/tasks/{task_id}/cancel", response_model=IncidentTaskItem)
def cancel_task(
    task_id: uuid.UUID,
    request: IncidentTaskCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_task_operations_permission),
):
    task, incident = _require_task_write_access(db=db, current_user=current_user, task_id=task_id)
    now_utc = datetime.now(timezone.utc)
    _validate_transition(current_status=_api_status(task.status), next_status="cancelled")
    _apply_status(
        task=task,
        next_status="cancelled",
        actor_user_id=current_user.id,
        now_utc=now_utc,
        cancel_reason=request.reason,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="task.cancel",
        event_type="incident_task_cancelled",
        outcome="success",
        incident_id=incident.incident_id,
        metadata={"task_id": str(task.task_id), "reason": request.reason},
    )
    create_event(
        db,
        incident_id=incident.incident_id,
        event_type=SystemEventType.INCIDENT_TASK_CANCELLED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=_event_payload(
            actor_id=current_user.id,
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            task_id=task.task_id,
            reason=request.reason,
            previous={"status": "open"},
            new={"status": "cancelled"},
        ),
    )

    return _to_task_item(task, now_utc=now_utc)


def _require_incident_access(
    *,
    db: Session,
    current_user: User,
    incident_id: uuid.UUID,
    write_access: bool,
) -> tuple[Incident, object]:
    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, incident_id=incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if write_access:
        require_policy(can_modify_incident(context, incident))
    else:
        require_policy(can_view_incident(context, incident))
    return incident, context


def _require_task_write_access(*, db: Session, current_user: User, task_id: uuid.UUID) -> tuple[CaseTask, Incident]:
    context = build_user_auth_context(db, current_user)
    org_ids = list(context.org_ids)
    task = (
        db.query(CaseTask)
        .join(Incident, Incident.incident_id == CaseTask.incident_id)
        .filter(
            CaseTask.task_id == task_id,
            or_(
                CaseTask.org_id.in_(org_ids),
                and_(CaseTask.org_id.is_(None), Incident.org_id.in_(org_ids)),
            ),
        )
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    incident = get_incident(db, incident_id=task.incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_modify_incident(context, incident))
    return task, incident


def _validate_transition(*, current_status: str, next_status: str) -> None:
    if current_status == next_status:
        return
    allowed_transitions = {
        "open": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    if next_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid task status transition from {current_status} to {next_status}",
        )


def _apply_status(
    *,
    task: CaseTask,
    next_status: str,
    actor_user_id: uuid.UUID,
    now_utc: datetime,
    cancel_reason: str | None = None,
) -> None:
    if next_status == "open":
        task.status = "open"
        task.completed_at_utc = None
        task.completed_by_user_id = None
        task.canceled_at_utc = None
        task.canceled_by_user_id = None
        task.canceled_reason = None
        return

    if next_status == "completed":
        task.status = "completed"
        task.completed_at_utc = now_utc
        task.completed_by_user_id = actor_user_id
        task.canceled_at_utc = None
        task.canceled_by_user_id = None
        task.canceled_reason = None
        return

    task.status = "canceled"
    task.canceled_at_utc = now_utc
    task.canceled_by_user_id = actor_user_id
    task.canceled_reason = cancel_reason
    task.completed_at_utc = None
    task.completed_by_user_id = None


def _api_status(status: str | None) -> str:
    if status == "canceled":
        return "cancelled"
    return str(status or "open")


def _to_task_item(task: CaseTask, *, now_utc: datetime) -> IncidentTaskItem:
    due_at_utc = _as_utc(task.due_at_utc)
    return IncidentTaskItem(
        task_id=task.task_id,
        incident_id=task.incident_id,
        title=task.title,
        description=task.description,
        task_type=str(task.task_type),
        status=_api_status(task.status),
        priority=str(task.priority),
        due_at_utc=due_at_utc,
        assigned_to_user_id=task.assigned_to_user_id,
        assigned_at_utc=task.assigned_at_utc,
        assigned_by_user_id=task.assigned_by_user_id,
        created_by_user_id=task.created_by_user_id,
        created_at_utc=task.created_at_utc,
        completed_at_utc=task.completed_at_utc,
        canceled_at_utc=task.canceled_at_utc,
        canceled_reason=task.canceled_reason,
        overdue=bool(due_at_utc and due_at_utc < now_utc and _api_status(task.status) == "open"),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _event_payload(
    *,
    actor_id: uuid.UUID,
    incident_id: uuid.UUID,
    org_id: uuid.UUID | None,
    task_id: uuid.UUID,
    reason: str | None,
    previous: dict[str, str | None],
    new: dict[str, str | None],
) -> dict[str, object]:
    return {
        "actor": {"type": "user", "id": str(actor_id)},
        "incident_id": str(incident_id),
        "org_id": str(org_id) if org_id else None,
        "task_id": str(task_id),
        "reason": reason,
        "previous": previous,
        "new": new,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
