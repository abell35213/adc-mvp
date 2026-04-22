"""Repository helpers for org entitlements, content, and readiness snapshots."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import (
    DemoScenario,
    DeploymentScopeSnapshot,
    ExpansionReadinessSnapshot,
    HelpArticle,
    HelpArticleView,
    HelpCategory,
    OrgPlanEntitlement,
    TrustSection,
)


def get_org_plan_entitlement(db: Session, org_id: _uuid.UUID) -> OrgPlanEntitlement | None:
    """Return the most recent active entitlement row for an org."""
    return (
        db.query(OrgPlanEntitlement)
        .filter(
            OrgPlanEntitlement.org_id == org_id,
            OrgPlanEntitlement.effective_to_utc.is_(None),
        )
        .order_by(OrgPlanEntitlement.effective_from_utc.desc())
        .first()
    )


def upsert_org_plan_entitlement(
    db: Session,
    org_id: _uuid.UUID,
    *,
    plan_code: str,
    billing_status: str = "active",
    core_incident_protocol: bool = True,
    entitlements_json: dict | None = None,
) -> OrgPlanEntitlement:
    """Create or update active org entitlement state."""
    row = get_org_plan_entitlement(db, org_id)
    if row is None:
        row = OrgPlanEntitlement(org_id=org_id)
        db.add(row)

    row.plan_code = plan_code
    row.billing_status = billing_status
    row.core_incident_protocol = core_incident_protocol
    row.entitlements_json = entitlements_json or {}

    db.commit()
    db.refresh(row)
    return row


def create_demo_scenario(
    db: Session,
    org_id: _uuid.UUID,
    *,
    scenario_key: str,
    name: str,
    description: str | None = None,
    seeded_by: str | None = None,
    seed_batch_id: str | None = None,
    seed_metadata_json: dict | None = None,
) -> DemoScenario:
    """Create an org-scoped demo scenario."""
    row = DemoScenario(
        org_id=org_id,
        scenario_key=scenario_key,
        name=name,
        description=description,
        seeded_by=seeded_by,
        seed_batch_id=seed_batch_id,
        seed_metadata_json=seed_metadata_json or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_demo_scenarios(db: Session, org_id: _uuid.UUID, *, active_only: bool = True) -> list[DemoScenario]:
    """List demo scenarios for an org."""
    query = db.query(DemoScenario).filter(DemoScenario.org_id == org_id)
    if active_only:
        query = query.filter(DemoScenario.is_active.is_(True))
    return query.order_by(DemoScenario.created_at_utc.desc()).all()


def create_help_category(
    db: Session,
    org_id: _uuid.UUID,
    *,
    slug: str,
    title: str,
    description: str | None = None,
    metadata_json: dict | None = None,
    sort_order: int = 0,
) -> HelpCategory:
    """Create a help category."""
    row = HelpCategory(
        org_id=org_id,
        slug=slug,
        title=title,
        description=description,
        metadata_json=metadata_json or {},
        sort_order=sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_help_article(
    db: Session,
    org_id: _uuid.UUID,
    *,
    slug: str,
    title: str,
    body_markdown: str,
    category_id: _uuid.UUID | None = None,
    summary: str | None = None,
    metadata_json: dict | None = None,
    created_by_user_id: _uuid.UUID | None = None,
) -> HelpArticle:
    """Create a help article."""
    row = HelpArticle(
        org_id=org_id,
        category_id=category_id,
        slug=slug,
        title=title,
        summary=summary,
        body_markdown=body_markdown,
        metadata_json=metadata_json or {},
        created_by_user_id=created_by_user_id,
        updated_by_user_id=created_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_help_articles(
    db: Session,
    org_id: _uuid.UUID,
    *,
    published_only: bool = True,
    category_id: _uuid.UUID | None = None,
) -> list[HelpArticle]:
    """List help articles for an org."""
    query = db.query(HelpArticle).filter(HelpArticle.org_id == org_id)
    if published_only:
        query = query.filter(HelpArticle.is_published.is_(True))
    if category_id:
        query = query.filter(HelpArticle.category_id == category_id)
    return query.order_by(HelpArticle.published_at_utc.desc().nullslast()).all()


def create_trust_section(
    db: Session,
    org_id: _uuid.UUID,
    *,
    slug: str,
    title: str,
    body_markdown: str,
    metadata_json: dict | None = None,
    sort_order: int = 0,
) -> TrustSection:
    """Create a trust section."""
    row = TrustSection(
        org_id=org_id,
        slug=slug,
        title=title,
        body_markdown=body_markdown,
        metadata_json=metadata_json or {},
        sort_order=sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_trust_sections(
    db: Session,
    org_id: _uuid.UUID,
    *,
    published_only: bool = True,
) -> list[TrustSection]:
    """List trust center sections."""
    query = db.query(TrustSection).filter(TrustSection.org_id == org_id)
    if published_only:
        query = query.filter(TrustSection.is_published.is_(True))
    return query.order_by(TrustSection.sort_order.asc(), TrustSection.created_at_utc.asc()).all()


def create_deployment_scope_snapshot(
    db: Session,
    org_id: _uuid.UUID,
    *,
    scope_version: str,
    scope_json: dict,
    captured_by_user_id: _uuid.UUID | None = None,
) -> DeploymentScopeSnapshot:
    """Persist a deployment scope snapshot."""
    row = DeploymentScopeSnapshot(
        org_id=org_id,
        scope_version=scope_version,
        scope_json=scope_json,
        captured_by_user_id=captured_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_deployment_scope_snapshot(
    db: Session, org_id: _uuid.UUID
) -> DeploymentScopeSnapshot | None:
    """Return the latest deployment scope snapshot for an org."""
    return (
        db.query(DeploymentScopeSnapshot)
        .filter(DeploymentScopeSnapshot.org_id == org_id)
        .order_by(DeploymentScopeSnapshot.captured_at_utc.desc())
        .first()
    )


def record_help_article_view(
    db: Session,
    org_id: _uuid.UUID,
    article_id: _uuid.UUID,
    *,
    viewer_user_id: _uuid.UUID | None = None,
    source: str | None = None,
    metadata_json: dict | None = None,
) -> HelpArticleView:
    """Record a help article view event."""
    row = HelpArticleView(
        org_id=org_id,
        article_id=article_id,
        viewer_user_id=viewer_user_id,
        source=source,
        metadata_json=metadata_json or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upsert_expansion_readiness_snapshot(
    db: Session,
    org_id: _uuid.UUID,
    *,
    scope_key: str,
    status: str,
    summary_json: dict,
    readiness_score: int | None = None,
) -> ExpansionReadinessSnapshot:
    """Upsert the optional cached expansion readiness summary."""
    row = (
        db.query(ExpansionReadinessSnapshot)
        .filter(
            ExpansionReadinessSnapshot.org_id == org_id,
            ExpansionReadinessSnapshot.scope_key == scope_key,
        )
        .first()
    )
    if row is None:
        row = ExpansionReadinessSnapshot(org_id=org_id, scope_key=scope_key)
        db.add(row)

    row.status = status
    row.summary_json = summary_json
    row.readiness_score = readiness_score

    db.commit()
    db.refresh(row)
    return row
