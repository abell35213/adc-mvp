"""Repository helpers for org notification recipients (crash-packet control file)."""

from __future__ import annotations

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import OrgNotificationRecipient


def list_active_email_recipients(
    db: Session, *, org_id: _uuid.UUID
) -> list[OrgNotificationRecipient]:
    """Return all active recipients for ``org_id`` whose channels include email."""
    rows = (
        db.query(OrgNotificationRecipient)
        .filter(
            OrgNotificationRecipient.org_id == org_id,
            OrgNotificationRecipient.active.is_(True),
        )
        .order_by(OrgNotificationRecipient.created_at_utc.asc())
        .all()
    )
    return [r for r in rows if "email" in (r.channels or [])]


def add_recipient(
    db: Session,
    *,
    org_id: _uuid.UUID,
    email: str,
    full_name: str | None = None,
    role_tag: str | None = None,
    channels: list[str] | None = None,
    active: bool = True,
) -> OrgNotificationRecipient:
    recipient = OrgNotificationRecipient(
        org_id=org_id,
        email=email.strip().lower(),
        full_name=full_name,
        role_tag=role_tag,
        channels=channels or ["email"],
        active=active,
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient


def deactivate_recipient(
    db: Session, *, org_id: _uuid.UUID, recipient_id: _uuid.UUID
) -> OrgNotificationRecipient | None:
    recipient = (
        db.query(OrgNotificationRecipient)
        .filter(
            OrgNotificationRecipient.org_id == org_id,
            OrgNotificationRecipient.id == recipient_id,
        )
        .first()
    )
    if recipient is None:
        return None
    recipient.active = False
    db.commit()
    db.refresh(recipient)
    return recipient
