"""Help center read routes."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.commercial.docs import (
    PUBLICATION_STATE_PUBLISHED,
    get_help_article,
    list_help_articles,
    list_help_categories,
    list_related_help_articles,
)
from app.commercial.enforcement import require_feature_enabled
from app.core.deps import get_current_user
from app.db.models import HelpArticle, HelpCategory, User
from app.db.repo.org_content import record_help_article_view
from app.db.session import get_db
from app.security.authn import build_user_auth_context

router = APIRouter(prefix="/help", tags=["help"])


class HelpArticleSummary(BaseModel):
    article_id: str
    category_id: str | None = None
    slug: str
    title: str
    summary: str | None = None
    metadata: dict
    is_published: bool


class HelpArticleDetail(HelpArticleSummary):
    body_markdown: str


class HelpCategoryItem(BaseModel):
    category_id: str
    slug: str
    title: str
    description: str | None = None
    sort_order: int
    metadata: dict
    is_published: bool


def _enforce_docs_read(db: Session, *, org_id: uuid.UUID, current_user: User) -> None:
    require_feature_enabled(
        db,
        org_id=org_id,
        actor_id=str(current_user.id),
        actor_role=current_user.role,
        feature_key="docs.playbooks",
        action="docs.read",
        allow_internal_override=True,
    )


def _serialize_article_summary(article: HelpArticle) -> HelpArticleSummary:
    return HelpArticleSummary(
        article_id=str(article.article_id),
        category_id=str(article.category_id) if article.category_id else None,
        slug=article.slug,
        title=article.title,
        summary=article.summary,
        metadata=article.metadata_json or {},
        is_published=bool(article.is_published),
    )


def _serialize_article_detail(article: HelpArticle) -> HelpArticleDetail:
    payload = _serialize_article_summary(article).model_dump()
    payload["body_markdown"] = article.body_markdown
    return HelpArticleDetail(**payload)


def _serialize_category(category: HelpCategory) -> HelpCategoryItem:
    return HelpCategoryItem(
        category_id=str(category.category_id),
        slug=category.slug,
        title=category.title,
        description=category.description,
        sort_order=category.sort_order,
        metadata=category.metadata_json or {},
        is_published=bool(category.is_published),
    )


@router.get("/articles", response_model=list[HelpArticleSummary])
def get_articles(
    category_id: uuid.UUID | None = Query(default=None),
    audience: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    publication_state: Literal["published", "draft", "all"] = Query(default=PUBLICATION_STATE_PUBLISHED),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _enforce_docs_read(db, org_id=org_id, current_user=current_user)

    rows = list_help_articles(
        db,
        org_id=org_id,
        publication_state=publication_state,
        category_id=category_id,
        audience=audience,
        tag=tag,
    )
    return [_serialize_article_summary(row) for row in rows]


@router.get("/articles/{article_id}", response_model=HelpArticleDetail)
def get_article_by_id(
    article_id: uuid.UUID,
    publication_state: Literal["published", "draft", "all"] = Query(default=PUBLICATION_STATE_PUBLISHED),
    source: str | None = Query(default="help_api"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _enforce_docs_read(db, org_id=org_id, current_user=current_user)

    row = get_help_article(
        db,
        org_id=org_id,
        article_id=article_id,
        publication_state=publication_state,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Help article not found",
        )

    record_help_article_view(
        db,
        org_id=org_id,
        article_id=row.article_id,
        viewer_user_id=current_user.id,
        source=source,
        metadata_json={
            "publication_state": publication_state,
        },
    )
    return _serialize_article_detail(row)


@router.get("/categories", response_model=list[HelpCategoryItem])
def get_categories(
    publication_state: Literal["published", "draft", "all"] = Query(default=PUBLICATION_STATE_PUBLISHED),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    org_id = context.org_ids[0]
    _enforce_docs_read(db, org_id=org_id, current_user=current_user)

    rows = list_help_categories(db, org_id=org_id, publication_state=publication_state)
    return [_serialize_category(row) for row in rows]


@router.get("/related", response_model=list[HelpArticleSummary])
def get_related_articles(
    context: str = Query(..., min_length=1),
    publication_state: Literal["published", "draft", "all"] = Query(default=PUBLICATION_STATE_PUBLISHED),
    limit: int = Query(default=5, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_context = build_user_auth_context(db, current_user)
    org_id = auth_context.org_ids[0]
    _enforce_docs_read(db, org_id=org_id, current_user=current_user)

    rows = list_related_help_articles(
        db,
        org_id=org_id,
        context=context,
        limit=limit,
        publication_state=publication_state,
    )
    return [_serialize_article_summary(row) for row in rows]
