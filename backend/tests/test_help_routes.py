"""Tests for help content service and API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.commercial.docs import publish_help_article
from app.core.security import create_access_token, hash_password
from app.db.models import AuditEvent, Base, HelpArticle, HelpArticleView, HelpCategory, Org, User, UserOrg
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def db_session():
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)
    session = test_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_org(db_session):
    org = Org(name="Help Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def org_admin_user(db_session, test_org):
    user = User(
        email="org-admin-help@example.com",
        password_hash=hash_password("testpass"),
        role="org_admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()
    return user


@pytest.fixture()
def support_admin_user(db_session, test_org):
    user = User(
        email="support-admin-help@example.com",
        password_hash=hash_password("testpass"),
        role="support_admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()
    return user


@pytest.fixture()
def help_seed(db_session, test_org, org_admin_user):
    category = HelpCategory(
        org_id=test_org.id,
        slug="safety",
        title="Safety",
        description="Safety workflows",
        sort_order=1,
        is_published=True,
        published_at_utc=datetime.now(timezone.utc),
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    published = HelpArticle(
        org_id=test_org.id,
        category_id=category.category_id,
        slug="incident-export",
        title="How to export an incident",
        summary="Export flow",
        body_markdown="Use the export button in the incident workspace.",
        is_published=True,
        published_at_utc=datetime.now(timezone.utc),
        metadata_json={"audiences": ["manager"], "tags": ["export", "incident"]},
        created_by_user_id=org_admin_user.id,
        updated_by_user_id=org_admin_user.id,
    )
    draft = HelpArticle(
        org_id=test_org.id,
        category_id=category.category_id,
        slug="draft-playbook",
        title="Draft playbook",
        summary="Draft-only content",
        body_markdown="internal draft",
        is_published=False,
        metadata_json={"audiences": ["support"], "tags": ["internal"]},
        created_by_user_id=org_admin_user.id,
        updated_by_user_id=org_admin_user.id,
    )
    db_session.add_all([published, draft])
    db_session.commit()
    db_session.refresh(published)
    db_session.refresh(draft)
    return {"category": category, "published": published, "draft": draft}


@pytest.fixture()
def client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth_headers(user):
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_help_routes_support_filtering_and_related(client, org_admin_user, help_seed):
    articles_resp = client.get(
        "/help/articles",
        headers=_auth_headers(org_admin_user),
        params={"audience": "manager", "tag": "export"},
    )
    assert articles_resp.status_code == 200
    payload = articles_resp.json()
    assert len(payload) == 1
    assert payload[0]["slug"] == "incident-export"

    drafts_resp = client.get(
        "/help/articles",
        headers=_auth_headers(org_admin_user),
        params={"publication_state": "draft"},
    )
    assert drafts_resp.status_code == 200
    assert [row["slug"] for row in drafts_resp.json()] == ["draft-playbook"]

    related_resp = client.get(
        "/help/related",
        headers=_auth_headers(org_admin_user),
        params={"context": "export"},
    )
    assert related_resp.status_code == 200
    related = related_resp.json()
    assert related
    assert related[0]["slug"] == "incident-export"

    categories_resp = client.get("/help/categories", headers=_auth_headers(org_admin_user))
    assert categories_resp.status_code == 200
    assert categories_resp.json()[0]["slug"] == "safety"


def test_help_article_read_records_view_event(client, db_session, org_admin_user, help_seed):
    article_id = help_seed["published"].article_id
    response = client.get(
        f"/help/articles/{article_id}",
        headers=_auth_headers(org_admin_user),
    )
    assert response.status_code == 200

    views = db_session.query(HelpArticleView).all()
    assert len(views) == 1
    assert views[0].article_id == article_id
    assert views[0].viewer_user_id == org_admin_user.id


def test_internal_publish_workflow_emits_audit_event(
    db_session,
    test_org,
    support_admin_user,
    help_seed,
):
    draft = help_seed["draft"]

    published = publish_help_article(
        db_session,
        org_id=test_org.id,
        article_id=draft.article_id,
        actor_id=support_admin_user.id,
        actor_role=support_admin_user.role,
    )

    assert published.is_published is True
    assert published.published_at_utc is not None

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "help_article_published")
        .order_by(AuditEvent.occurred_at_utc.desc())
        .first()
    )
    assert event is not None
    assert event.metadata_json["article_id"] == str(draft.article_id)
