"""API idempotency helpers backed by event payload metadata."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Event


@dataclass(frozen=True)
class IdempotencyContext:
    raw_key: str
    hashed_key: str


def optional_idempotency_key(idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> IdempotencyContext | None:
    """Read optional idempotency key from API header."""
    if not idempotency_key:
        return None
    normalized = idempotency_key.strip()
    if not normalized:
        return None
    return IdempotencyContext(
        raw_key=normalized,
        hashed_key=hmac.new(settings.JWT_SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest(),
    )


def require_idempotency_key(idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> IdempotencyContext:
    context = optional_idempotency_key(idempotency_key)
    if context is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    return context


def find_event_by_idempotency(
    db: Session,
    *,
    event_type: str,
    actor_type: str,
    actor_id: str,
    idempotency_key_hash: str,
    incident_id=None,
):
    events = (
        db.query(Event)
        .filter(
            Event.event_type == event_type,
            Event.actor_type == actor_type,
            Event.actor_id == actor_id,
            Event.incident_id == incident_id,
        )
        .order_by(Event.created_at_utc.desc())
        .all()
    )
    for ev in events:
        payload = ev.payload or {}
        if payload.get("idempotency_key_hash") == idempotency_key_hash:
            return ev
    return None
