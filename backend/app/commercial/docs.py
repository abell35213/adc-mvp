"""Documentation center content service and publication workflows."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.emitter import emit_audit_event
from app.db.models import HelpArticle, HelpCategory

DOCS_FEATURES: tuple[str, ...] = (
    "docs.playbooks",
    "docs.api_reference",
)

PUBLICATION_STATE_PUBLISHED = "published"
PUBLICATION_STATE_DRAFT = "draft"
PUBLICATION_STATE_ALL = "all"
_VALID_PUBLICATION_STATES = {
    PUBLICATION_STATE_PUBLISHED,
    PUBLICATION_STATE_DRAFT,
    PUBLICATION_STATE_ALL,
}

_INTERNAL_DOCS_ROLES = {"system_admin", "support_admin", "support_agent"}


def _is_internal_docs_actor(role: str | None) -> bool:
    return (role or "").strip().lower() in _INTERNAL_DOCS_ROLES


def _normalize_publication_state(publication_state: str) -> str:
    normalized = (publication_state or PUBLICATION_STATE_PUBLISHED).strip().lower()
    if normalized not in _VALID_PUBLICATION_STATES:
        raise ValueError(
            "publication_state must be one of: published, draft, all"
        )
    return normalized


def _matches_metadata_values(metadata: dict | None, key: str, expected: str | None) -> bool:
    if not expected:
        return True
    value = (metadata or {}).get(key)
    if value is None:
        return False
    expected_lower = expected.strip().lower()
    if isinstance(value, str):
        return expected_lower == value.strip().lower()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        normalized_values = {str(item).strip().lower() for item in value}
        return expected_lower in normalized_values
    return False


def list_help_articles(
    db: Session,
    *,
    org_id: uuid.UUID,
    publication_state: str = PUBLICATION_STATE_PUBLISHED,
    category_id: uuid.UUID | None = None,
    audience: str | None = None,
    tag: str | None = None,
) -> list[HelpArticle]:
    """List help articles with publication/category/audience/tag filtering."""
    state = _normalize_publication_state(publication_state)

    query = db.query(HelpArticle).filter(HelpArticle.org_id == org_id)
    if state == PUBLICATION_STATE_PUBLISHED:
        query = query.filter(HelpArticle.is_published.is_(True))
    elif state == PUBLICATION_STATE_DRAFT:
        query = query.filter(HelpArticle.is_published.is_(False))

    if category_id is not None:
        query = query.filter(HelpArticle.category_id == category_id)

    rows = query.order_by(HelpArticle.published_at_utc.desc().nullslast(), HelpArticle.created_at_utc.desc()).all()
    return [
        row
        for row in rows
        if _matches_metadata_values(row.metadata_json, "audiences", audience)
        and _matches_metadata_values(row.metadata_json, "tags", tag)
    ]


def get_help_article(
    db: Session,
    *,
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    publication_state: str = PUBLICATION_STATE_PUBLISHED,
) -> HelpArticle | None:
    """Get a single help article for org scope and publication-state."""
    state = _normalize_publication_state(publication_state)
    query = db.query(HelpArticle).filter(
        HelpArticle.org_id == org_id,
        HelpArticle.article_id == article_id,
    )
    if state == PUBLICATION_STATE_PUBLISHED:
        query = query.filter(HelpArticle.is_published.is_(True))
    elif state == PUBLICATION_STATE_DRAFT:
        query = query.filter(HelpArticle.is_published.is_(False))
    return query.first()


def list_help_categories(
    db: Session,
    *,
    org_id: uuid.UUID,
    publication_state: str = PUBLICATION_STATE_PUBLISHED,
) -> list[HelpCategory]:
    """List categories with publication-state filtering."""
    state = _normalize_publication_state(publication_state)
    query = db.query(HelpCategory).filter(HelpCategory.org_id == org_id)
    if state == PUBLICATION_STATE_PUBLISHED:
        query = query.filter(HelpCategory.is_published.is_(True))
    elif state == PUBLICATION_STATE_DRAFT:
        query = query.filter(HelpCategory.is_published.is_(False))
    return query.order_by(HelpCategory.sort_order.asc(), HelpCategory.created_at_utc.asc()).all()


def list_related_help_articles(
    db: Session,
    *,
    org_id: uuid.UUID,
    context: str,
    limit: int = 5,
    publication_state: str = PUBLICATION_STATE_PUBLISHED,
) -> list[HelpArticle]:
    """Find related help articles by lightweight context matching."""
    lowered_context = context.strip().lower()
    if not lowered_context:
        return []

    rows = list_help_articles(
        db,
        org_id=org_id,
        publication_state=publication_state,
    )

    def _score(article: HelpArticle) -> int:
        score = 0
        title = (article.title or "").lower()
        summary = (article.summary or "").lower()
        body = (article.body_markdown or "").lower()
        if lowered_context in title:
            score += 3
        if lowered_context in summary:
            score += 2
        if lowered_context in body:
            score += 1
        metadata = article.metadata_json or {}
        tags = metadata.get("tags") or []
        audiences = metadata.get("audiences") or []
        values = {str(value).strip().lower() for value in [*tags, *audiences]}
        if lowered_context in values:
            score += 4
        return score

    scored = [(article, _score(article)) for article in rows]
    scored = [pair for pair in scored if pair[1] > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [article for article, _ in scored[:limit]]


def publish_help_article(
    db: Session,
    *,
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
) -> HelpArticle:
    """Publish a help article (internal workflow only) and write audit event."""
    if not _is_internal_docs_actor(actor_role):
        raise PermissionError("Internal role required to publish help articles")

    article = get_help_article(
        db,
        org_id=org_id,
        article_id=article_id,
        publication_state=PUBLICATION_STATE_ALL,
    )
    if article is None:
        raise ValueError("Article not found")

    now = datetime.now(timezone.utc)
    article.is_published = True
    article.published_at_utc = now
    article.unpublished_at_utc = None
    article.updated_by_user_id = actor_id

    db.add(article)
    db.commit()
    db.refresh(article)

    emit_audit_event(
        db,
        org_id=org_id,
        actor_type="user",
        actor_id=str(actor_id),
        action="help.article.publish",
        event_type="help_article_published",
        outcome="success",
        metadata={
            "article_id": str(article.article_id),
            "slug": article.slug,
            "state": "published",
        },
    )
    return article


def unpublish_help_article(
    db: Session,
    *,
    org_id: uuid.UUID,
    article_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
) -> HelpArticle:
    """Unpublish a help article (internal workflow only)."""
    if not _is_internal_docs_actor(actor_role):
        raise PermissionError("Internal role required to unpublish help articles")

    article = get_help_article(
        db,
        org_id=org_id,
        article_id=article_id,
        publication_state=PUBLICATION_STATE_ALL,
    )
    if article is None:
        raise ValueError("Article not found")

    now = datetime.now(timezone.utc)
    article.is_published = False
    article.unpublished_at_utc = now
    article.updated_by_user_id = actor_id

    db.add(article)
    db.commit()
    db.refresh(article)
    return article
