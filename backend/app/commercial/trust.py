"""Trust center content service and publication workflows."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.audit.emitter import emit_audit_event
from app.db.models import TrustSection

DeploymentScope = Literal[
    "single_site",
    "multi_site",
    "regional",
    "national",
    "global",
]

DEPLOYMENT_SCOPE_STATES: tuple[DeploymentScope, ...] = (
    "single_site",
    "multi_site",
    "regional",
    "national",
    "global",
)

TRUST_FEATURES: tuple[str, ...] = (
    "trust.sso",
    "trust.audit_controls",
)

TRUST_CONTENT_FEATURE = "trust.audit_controls"

PUBLICATION_STATE_PUBLISHED = "published"
PUBLICATION_STATE_DRAFT = "draft"
PUBLICATION_STATE_ALL = "all"

_VALID_PUBLICATION_STATES = {
    PUBLICATION_STATE_PUBLISHED,
    PUBLICATION_STATE_DRAFT,
    PUBLICATION_STATE_ALL,
}

_INTERNAL_TRUST_ROLES = {"system_admin", "support_admin"}


def _normalize_publication_state(publication_state: str) -> str:
    normalized = (publication_state or PUBLICATION_STATE_PUBLISHED).strip().lower()
    if normalized not in _VALID_PUBLICATION_STATES:
        raise ValueError("publication_state must be one of: published, draft, all")
    return normalized


def _is_internal_trust_actor(role: str | None) -> bool:
    return (role or "").strip().lower() in _INTERNAL_TRUST_ROLES


def _matches_audience(metadata: dict | None, audience: str | None) -> bool:
    if not audience:
        return True
    value = (metadata or {}).get("audiences")
    if value is None:
        return False
    expected = audience.strip().lower()
    if isinstance(value, str):
        return expected == value.strip().lower()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        normalized = {str(item).strip().lower() for item in value}
        return expected in normalized
    return False


def list_trust_sections(
    db: Session,
    *,
    org_id: uuid.UUID,
    publication_state: str = PUBLICATION_STATE_PUBLISHED,
    audience: str | None = None,
) -> list[TrustSection]:
    """List trust sections with publication/audience filtering."""
    state = _normalize_publication_state(publication_state)

    query = db.query(TrustSection).filter(TrustSection.org_id == org_id)
    if state == PUBLICATION_STATE_PUBLISHED:
        query = query.filter(TrustSection.is_published.is_(True))
    elif state == PUBLICATION_STATE_DRAFT:
        query = query.filter(TrustSection.is_published.is_(False))

    rows = query.order_by(TrustSection.sort_order.asc(), TrustSection.created_at_utc.asc()).all()
    return [row for row in rows if _matches_audience(row.metadata_json, audience)]


def get_trust_summary(
    db: Session,
    *,
    org_id: uuid.UUID,
    audience: str | None = None,
) -> dict[str, Any]:
    """Return a simple trust center summary for the active published scope."""
    sections = list_trust_sections(
        db,
        org_id=org_id,
        publication_state=PUBLICATION_STATE_PUBLISHED,
        audience=audience,
    )
    published_at_values = [section.published_at_utc for section in sections if section.published_at_utc is not None]
    return {
        "section_count": len(sections),
        "section_slugs": [section.slug for section in sections],
        "latest_published_at_utc": max(published_at_values).isoformat() if published_at_values else None,
        "audience": audience,
    }


def _emit_trust_center_updated(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    metadata: dict[str, Any],
) -> None:
    emit_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(actor_id),
        action=action,
        event_type="trust_center_updated",
        outcome="success",
        metadata=metadata,
    )


def upsert_trust_section(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
    section_id: uuid.UUID | None,
    slug: str,
    title: str,
    body_markdown: str,
    sort_order: int = 0,
    metadata_json: dict | None = None,
) -> TrustSection:
    """Create or update trust section draft content and emit audit event."""
    if not _is_internal_trust_actor(actor_role):
        raise PermissionError("Internal admin role required to update trust sections")

    row: TrustSection | None = None
    if section_id is not None:
        row = (
            db.query(TrustSection)
            .filter(TrustSection.org_id == org_id, TrustSection.section_id == section_id)
            .first()
        )
    if row is None:
        row = (
            db.query(TrustSection)
            .filter(TrustSection.org_id == org_id, TrustSection.slug == slug)
            .first()
        )

    creating = row is None
    if creating:
        row = TrustSection(org_id=org_id, slug=slug)

    before = {
        "title": row.title if not creating else None,
        "sort_order": row.sort_order if not creating else None,
        "audiences": (row.metadata_json or {}).get("audiences") if not creating else None,
    }

    row.title = title
    row.body_markdown = body_markdown
    row.sort_order = int(sort_order)
    row.metadata_json = dict(metadata_json or {})

    db.add(row)
    db.commit()
    db.refresh(row)

    _emit_trust_center_updated(
        db,
        org_id=org_id,
        actor_id=actor_id,
        action="trust.section.create" if creating else "trust.section.update",
        metadata={
            "section_id": str(row.section_id),
            "slug": row.slug,
            "before": before,
            "after": {
                "title": row.title,
                "sort_order": row.sort_order,
                "audiences": (row.metadata_json or {}).get("audiences"),
            },
            "config_changed": True,
        },
    )
    return row


def publish_trust_section(
    db: Session,
    *,
    org_id: uuid.UUID,
    section_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
) -> TrustSection:
    """Publish trust section content and emit trust_center_updated audit event."""
    if not _is_internal_trust_actor(actor_role):
        raise PermissionError("Internal admin role required to publish trust sections")

    section = (
        db.query(TrustSection)
        .filter(TrustSection.org_id == org_id, TrustSection.section_id == section_id)
        .first()
    )
    if section is None:
        raise ValueError("Trust section not found")

    now = datetime.now(timezone.utc)
    section.is_published = True
    section.published_at_utc = now
    section.unpublished_at_utc = None

    db.add(section)
    db.commit()
    db.refresh(section)

    _emit_trust_center_updated(
        db,
        org_id=org_id,
        actor_id=actor_id,
        action="trust.section.publish",
        metadata={
            "section_id": str(section.section_id),
            "slug": section.slug,
            "state": "published",
            "published": True,
        },
    )
    return section


def unpublish_trust_section(
    db: Session,
    *,
    org_id: uuid.UUID,
    section_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
) -> TrustSection:
    """Unpublish trust section content and emit trust_center_updated audit event."""
    if not _is_internal_trust_actor(actor_role):
        raise PermissionError("Internal admin role required to publish trust sections")

    section = (
        db.query(TrustSection)
        .filter(TrustSection.org_id == org_id, TrustSection.section_id == section_id)
        .first()
    )
    if section is None:
        raise ValueError("Trust section not found")

    now = datetime.now(timezone.utc)
    section.is_published = False
    section.unpublished_at_utc = now

    db.add(section)
    db.commit()
    db.refresh(section)

    _emit_trust_center_updated(
        db,
        org_id=org_id,
        actor_id=actor_id,
        action="trust.section.unpublish",
        metadata={
            "section_id": str(section.section_id),
            "slug": section.slug,
            "state": "draft",
            "published": False,
        },
    )
    return section
