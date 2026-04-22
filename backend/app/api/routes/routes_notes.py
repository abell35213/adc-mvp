"""Incident notes CRUD routes (internal-only)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.schemas import (
    IncidentNoteCreateRequest,
    IncidentNoteDeleteRequest,
    IncidentNoteItem,
    IncidentNotePatchRequest,
    IncidentNotesResponse,
)
from app.audit.emitter import emit_audit_event
from app.core.deps import (
    require_note_operations_permission,
    require_workspace_view_permission,
)
from app.db.models import CaseNote, User
from app.db.repo.events import create_event
from app.db.repo.incidents import get_incident
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.security.authn import build_user_auth_context
from app.security.authz import can_modify_incident, can_view_incident, require_policy

router = APIRouter()


@router.get("/incidents/{incident_id}/notes", response_model=IncidentNotesResponse)
def list_incident_notes(
    incident_id: uuid.UUID,
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, incident_id=incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_view_incident(context, incident))

    query = db.query(CaseNote).filter(CaseNote.incident_id == incident.incident_id)
    if not include_deleted:
        query = query.filter(or_(CaseNote.is_deleted.is_(False), CaseNote.is_deleted.is_(None)))
    notes = query.order_by(CaseNote.created_at_utc.desc()).all()
    return IncidentNotesResponse(items=[_to_note_item(note) for note in notes])


@router.post("/incidents/{incident_id}/notes", response_model=IncidentNoteItem)
def create_incident_note(
    incident_id: uuid.UUID,
    request: IncidentNoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, incident_id=incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_modify_incident(context, incident))

    note = CaseNote(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        body=request.body,
        note_type=request.note_type,
        tags_json=list(request.tags or []),
        created_by_user_id=current_user.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    event_payload = _event_payload(
        actor_id=current_user.id,
        incident_id=incident.incident_id,
        org_id=incident.org_id,
        reason=None,
        previous={"body": None, "note_type": None},
        new={"body": note.body, "note_type": str(note.note_type)},
        note_id=note.note_id,
    )
    create_event(
        db,
        incident_id=incident.incident_id,
        event_type=SystemEventType.INCIDENT_NOTE_ADDED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload=event_payload,
    )
    emit_audit_event(
        db,
        org_id=incident.org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="incident.note.add",
        event_type="incident_note_added",
        outcome="success",
        incident_id=incident.incident_id,
        metadata=event_payload,
    )
    return _to_note_item(note)


@router.patch("/incidents/{incident_id}/notes", response_model=IncidentNoteItem)
def patch_incident_note(
    incident_id: uuid.UUID,
    request: IncidentNotePatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, incident_id=incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_modify_incident(context, incident))

    note = (
        db.query(CaseNote)
        .filter(CaseNote.incident_id == incident.incident_id, CaseNote.note_id == request.note_id)
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    if bool(note.is_deleted):
        raise HTTPException(status_code=409, detail="Cannot edit deleted note")
    require_policy(_can_edit_note(current_user=current_user, note=note))

    previous_values = {
        "body": note.body,
        "note_type": str(note.note_type),
        "tags": list(note.tags_json or []),
    }
    did_change = False
    if request.body is not None:
        note.body = request.body
        did_change = True
    if request.note_type is not None:
        note.note_type = request.note_type
        did_change = True
    if request.tags is not None:
        note.tags_json = list(request.tags)
        did_change = True

    if did_change:
        note.edited_by_user_id = current_user.id
        note.edited_at_utc = datetime.now(timezone.utc)

    db.add(note)
    db.commit()
    db.refresh(note)
    if did_change:
        event_payload = _event_payload(
            actor_id=current_user.id,
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            reason="edit",
            previous=previous_values,
            new={
                "body": note.body,
                "note_type": str(note.note_type),
                "tags": list(note.tags_json or []),
            },
            note_id=note.note_id,
        )
        create_event(
            db,
            incident_id=incident.incident_id,
            event_type=SystemEventType.INCIDENT_NOTE_EDITED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload=event_payload,
        )
        emit_audit_event(
            db,
            org_id=incident.org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="incident.note.edit",
            event_type="incident_note_edited",
            outcome="success",
            incident_id=incident.incident_id,
            metadata=event_payload,
        )
    return _to_note_item(note)


@router.delete("/incidents/{incident_id}/notes", response_model=IncidentNoteItem)
def delete_incident_note(
    incident_id: uuid.UUID,
    request: IncidentNoteDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    context = build_user_auth_context(db, current_user)
    incident = get_incident(db, incident_id=incident_id, org_ids=list(context.org_ids))
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_modify_incident(context, incident))

    note = (
        db.query(CaseNote)
        .filter(CaseNote.incident_id == incident.incident_id, CaseNote.note_id == request.note_id)
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    require_policy(_can_edit_note(current_user=current_user, note=note))

    if not bool(note.is_deleted):
        previous_values = {
            "body": note.body,
            "note_type": str(note.note_type),
            "tags": list(note.tags_json or []),
            "is_deleted": False,
        }
        note.is_deleted = True
        note.deleted_by_user_id = current_user.id
        note.deleted_at_utc = datetime.now(timezone.utc)
        db.add(note)
        db.commit()
        db.refresh(note)
        event_payload = _event_payload(
            actor_id=current_user.id,
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            reason="delete",
            previous=previous_values,
            new={"is_deleted": True},
            note_id=note.note_id,
        )
        create_event(
            db,
            incident_id=incident.incident_id,
            event_type=SystemEventType.INCIDENT_NOTE_DELETED,
            actor_type="user",
            actor_id=str(current_user.id),
            payload=event_payload,
        )
        emit_audit_event(
            db,
            org_id=incident.org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="incident.note.delete",
            event_type="incident_note_deleted",
            outcome="success",
            incident_id=incident.incident_id,
            metadata=event_payload,
        )
    return _to_note_item(note)


def _event_payload(
    *,
    actor_id: uuid.UUID,
    incident_id: uuid.UUID,
    org_id: uuid.UUID | None,
    reason: str | None,
    previous: dict[str, object],
    new: dict[str, object],
    note_id: uuid.UUID,
) -> dict[str, object]:
    return {
        "actor": {"type": "user", "id": str(actor_id)},
        "incident_id": str(incident_id),
        "org_id": str(org_id) if org_id else None,
        "note_id": str(note_id),
        "reason": reason,
        "previous": previous,
        "new": new,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _can_edit_note(*, current_user: User, note: CaseNote) -> bool:
    if current_user.role in {"org_admin", "system_admin"}:
        return True
    return note.created_by_user_id == current_user.id


def _to_note_item(note: CaseNote) -> IncidentNoteItem:
    return IncidentNoteItem(
        note_id=note.note_id,
        incident_id=note.incident_id,
        body=note.body,
        note_type=str(note.note_type or "standard"),
        tags=list(note.tags_json or []),
        created_by_user_id=note.created_by_user_id,
        created_at_utc=note.created_at_utc,
        edited=bool(note.edited_at_utc),
        edited_by_user_id=note.edited_by_user_id,
        edited_at_utc=note.edited_at_utc,
        updated_at_utc=note.updated_at_utc,
        is_deleted=bool(note.is_deleted),
        deleted_by_user_id=note.deleted_by_user_id,
        deleted_at_utc=note.deleted_at_utc,
    )
