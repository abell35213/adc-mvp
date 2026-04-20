"""Trust center read + internal content management routes."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.commercial.enforcement import require_feature_enabled
from app.commercial.trust import (
    PUBLICATION_STATE_PUBLISHED,
    TRUST_CONTENT_FEATURE,
    get_trust_summary,
    list_trust_sections,
    publish_trust_section,
    unpublish_trust_section,
    upsert_trust_section,
)
from app.core.deps import get_current_user
from app.db.models import TrustSection, User
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.permissions import Capability, has_capability

router = APIRouter(prefix="/trust", tags=["trust"])

class TrustSectionItem(BaseModel):
    section_id: str
    slug: str
    title: str
    body_markdown: str
    sort_order: int
    metadata: dict
    is_published: bool


class TrustSummaryResponse(BaseModel):
    section_count: int
    section_slugs: list[str]
    latest_published_at_utc: str | None
    audience: str | None = None


class TrustSectionUpsertRequest(BaseModel):
    section_id: uuid.UUID | None = None
    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body_markdown: str = Field(min_length=1)
    sort_order: int = 0
    metadata: dict = Field(default_factory=dict)


def _resolve_org_id(db: Session, current_user: User) -> uuid.UUID:
    context = build_user_auth_context(db, current_user)
    return context.org_ids[0]


def _enforce_trust_read(db: Session, *, org_id: uuid.UUID, current_user: User) -> None:
    require_feature_enabled(
        db,
        org_id=org_id,
        actor_id=str(current_user.id),
        actor_role=current_user.role,
        feature_key=TRUST_CONTENT_FEATURE,
        action="trust.read",
        allow_internal_override=True,
    )


def _serialize_section(section: TrustSection) -> TrustSectionItem:
    return TrustSectionItem(
        section_id=str(section.section_id),
        slug=section.slug,
        title=section.title,
        body_markdown=section.body_markdown,
        sort_order=section.sort_order,
        metadata=section.metadata_json or {},
        is_published=bool(section.is_published),
    )


def _require_internal_publish_capability(current_user: User) -> None:
    if not has_capability(current_user.role, Capability.TRUST_DOCS_PUBLISH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


@router.get("/sections", response_model=list[TrustSectionItem])
def get_sections(
    publication_state: Literal["published", "draft", "all"] = Query(default=PUBLICATION_STATE_PUBLISHED),
    audience: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _resolve_org_id(db, current_user)
    _enforce_trust_read(db, org_id=org_id, current_user=current_user)

    rows = list_trust_sections(
        db,
        org_id=org_id,
        publication_state=publication_state,
        audience=audience,
    )
    return [_serialize_section(row) for row in rows]


@router.get("/summary", response_model=TrustSummaryResponse)
def get_summary(
    audience: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _resolve_org_id(db, current_user)
    _enforce_trust_read(db, org_id=org_id, current_user=current_user)
    return TrustSummaryResponse(**get_trust_summary(db, org_id=org_id, audience=audience))


@router.put("/internal/sections", response_model=TrustSectionItem)
def put_internal_section(
    payload: TrustSectionUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_internal_publish_capability(current_user)
    org_id = _resolve_org_id(db, current_user)
    row = upsert_trust_section(
        db,
        org_id=org_id,
        actor_id=current_user.id,
        actor_role=current_user.role,
        section_id=payload.section_id,
        slug=payload.slug,
        title=payload.title,
        body_markdown=payload.body_markdown,
        sort_order=payload.sort_order,
        metadata_json=payload.metadata,
    )
    return _serialize_section(row)


@router.post("/internal/sections/{section_id}/publish", response_model=TrustSectionItem)
def post_publish_section(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_internal_publish_capability(current_user)
    org_id = _resolve_org_id(db, current_user)
    try:
        row = publish_trust_section(
            db,
            org_id=org_id,
            section_id=section_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_section(row)


@router.post("/internal/sections/{section_id}/unpublish", response_model=TrustSectionItem)
def post_unpublish_section(
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_internal_publish_capability(current_user)
    org_id = _resolve_org_id(db, current_user)
    try:
        row = unpublish_trust_section(
            db,
            org_id=org_id,
            section_id=section_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_section(row)
