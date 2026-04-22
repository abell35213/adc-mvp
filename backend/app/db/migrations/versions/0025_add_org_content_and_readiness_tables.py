"""add org content, entitlement, and readiness tables

Revision ID: 0025_add_org_content_and_readiness_tables
Revises: 0024_add_org_export_validation_runs
Create Date: 2026-04-19 00:00:00.000000
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "org_plan_entitlements",
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_code", sa.Text(), nullable=False, server_default="starter"),
        sa.Column("billing_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("core_incident_protocol", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("entitlements_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("effective_from_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("effective_to_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("entitlement_id"),
    )
    op.create_index("ix_org_plan_entitlements_org_id", "org_plan_entitlements", ["org_id"], unique=False)
    op.create_index(
        "ix_org_plan_entitlements_org_current",
        "org_plan_entitlements",
        ["org_id", "effective_to_utc"],
        unique=False,
    )

    bind = op.get_bind()
    org_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM orgs")).fetchall()]
    if org_ids:
        op.bulk_insert(
            sa.table(
                "org_plan_entitlements",
                sa.column("entitlement_id", postgresql.UUID(as_uuid=True)),
                sa.column("org_id", postgresql.UUID(as_uuid=True)),
                sa.column("plan_code", sa.Text()),
                sa.column("billing_status", sa.Text()),
                sa.column("core_incident_protocol", sa.Boolean()),
                sa.column("entitlements_json", postgresql.JSONB(astext_type=sa.Text())),
            ),
            [
                {
                    "entitlement_id": uuid.uuid4(),
                    "org_id": org_id,
                    "plan_code": "starter",
                    "billing_status": "active",
                    "core_incident_protocol": True,
                    "entitlements_json": {},
                }
                for org_id in org_ids
            ],
        )

    op.create_table(
        "demo_scenarios",
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("seeded_by", sa.Text(), nullable=True),
        sa.Column("seed_batch_id", sa.Text(), nullable=True),
        sa.Column("seed_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("scenario_id"),
    )
    op.create_index("ix_demo_scenarios_org_id", "demo_scenarios", ["org_id"], unique=False)
    op.create_index("ix_demo_scenarios_org_key", "demo_scenarios", ["org_id", "scenario_key"], unique=True)
    op.create_index("ix_demo_scenarios_org_active", "demo_scenarios", ["org_id", "is_active"], unique=False)

    op.create_table(
        "help_categories",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("unpublished_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("category_id"),
    )
    op.create_index("ix_help_categories_org_id", "help_categories", ["org_id"], unique=False)
    op.create_index("ix_help_categories_is_published", "help_categories", ["is_published"], unique=False)
    op.create_index("ix_help_categories_org_slug", "help_categories", ["org_id", "slug"], unique=True)
    op.create_index(
        "ix_help_categories_org_published",
        "help_categories",
        ["org_id", "is_published", "sort_order"],
        unique=False,
    )

    op.create_table(
        "help_articles",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("unpublished_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["category_id"], ["help_categories.category_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("article_id"),
    )
    op.create_index("ix_help_articles_org_id", "help_articles", ["org_id"], unique=False)
    op.create_index("ix_help_articles_category_id", "help_articles", ["category_id"], unique=False)
    op.create_index("ix_help_articles_is_published", "help_articles", ["is_published"], unique=False)
    op.create_index("ix_help_articles_published_at_utc", "help_articles", ["published_at_utc"], unique=False)
    op.create_index("ix_help_articles_org_slug", "help_articles", ["org_id", "slug"], unique=True)
    op.create_index(
        "ix_help_articles_org_published_category",
        "help_articles",
        ["org_id", "is_published", "category_id", "published_at_utc"],
        unique=False,
    )

    op.create_table(
        "trust_sections",
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("unpublished_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("section_id"),
    )
    op.create_index("ix_trust_sections_org_id", "trust_sections", ["org_id"], unique=False)
    op.create_index("ix_trust_sections_is_published", "trust_sections", ["is_published"], unique=False)
    op.create_index("ix_trust_sections_published_at_utc", "trust_sections", ["published_at_utc"], unique=False)
    op.create_index("ix_trust_sections_org_slug", "trust_sections", ["org_id", "slug"], unique=True)
    op.create_index(
        "ix_trust_sections_org_published_sort",
        "trust_sections",
        ["org_id", "is_published", "sort_order", "published_at_utc"],
        unique=False,
    )

    op.create_table(
        "deployment_scope_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_version", sa.Text(), nullable=False),
        sa.Column("scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("captured_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("captured_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["captured_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index("ix_deployment_scope_snapshots_org_id", "deployment_scope_snapshots", ["org_id"], unique=False)
    op.create_index(
        "ix_deployment_scope_snapshots_org_captured",
        "deployment_scope_snapshots",
        ["org_id", "captured_at_utc"],
        unique=False,
    )

    op.create_table(
        "help_article_views",
        sa.Column("view_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("viewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("viewed_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["article_id"], ["help_articles.article_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["viewer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("view_id"),
    )
    op.create_index("ix_help_article_views_org_id", "help_article_views", ["org_id"], unique=False)
    op.create_index("ix_help_article_views_article_id", "help_article_views", ["article_id"], unique=False)
    op.create_index("ix_help_article_views_viewer_user_id", "help_article_views", ["viewer_user_id"], unique=False)
    op.create_index("ix_help_article_views_viewed_at_utc", "help_article_views", ["viewed_at_utc"], unique=False)
    op.create_index(
        "ix_help_article_views_org_article_viewed",
        "help_article_views",
        ["org_id", "article_id", "viewed_at_utc"],
        unique=False,
    )

    op.create_table(
        "expansion_readiness_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("computed_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index("ix_expansion_readiness_snapshots_org_id", "expansion_readiness_snapshots", ["org_id"], unique=False)
    op.create_index(
        "ix_expansion_readiness_snapshots_org_scope",
        "expansion_readiness_snapshots",
        ["org_id", "scope_key"],
        unique=True,
    )
    op.create_index(
        "ix_expansion_readiness_snapshots_org_computed",
        "expansion_readiness_snapshots",
        ["org_id", "computed_at_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_expansion_readiness_snapshots_org_computed", table_name="expansion_readiness_snapshots")
    op.drop_index("ix_expansion_readiness_snapshots_org_scope", table_name="expansion_readiness_snapshots")
    op.drop_index("ix_expansion_readiness_snapshots_org_id", table_name="expansion_readiness_snapshots")
    op.drop_table("expansion_readiness_snapshots")

    op.drop_index("ix_help_article_views_org_article_viewed", table_name="help_article_views")
    op.drop_index("ix_help_article_views_viewed_at_utc", table_name="help_article_views")
    op.drop_index("ix_help_article_views_viewer_user_id", table_name="help_article_views")
    op.drop_index("ix_help_article_views_article_id", table_name="help_article_views")
    op.drop_index("ix_help_article_views_org_id", table_name="help_article_views")
    op.drop_table("help_article_views")

    op.drop_index("ix_deployment_scope_snapshots_org_captured", table_name="deployment_scope_snapshots")
    op.drop_index("ix_deployment_scope_snapshots_org_id", table_name="deployment_scope_snapshots")
    op.drop_table("deployment_scope_snapshots")

    op.drop_index("ix_trust_sections_org_published_sort", table_name="trust_sections")
    op.drop_index("ix_trust_sections_org_slug", table_name="trust_sections")
    op.drop_index("ix_trust_sections_published_at_utc", table_name="trust_sections")
    op.drop_index("ix_trust_sections_is_published", table_name="trust_sections")
    op.drop_index("ix_trust_sections_org_id", table_name="trust_sections")
    op.drop_table("trust_sections")

    op.drop_index("ix_help_articles_org_published_category", table_name="help_articles")
    op.drop_index("ix_help_articles_org_slug", table_name="help_articles")
    op.drop_index("ix_help_articles_published_at_utc", table_name="help_articles")
    op.drop_index("ix_help_articles_is_published", table_name="help_articles")
    op.drop_index("ix_help_articles_category_id", table_name="help_articles")
    op.drop_index("ix_help_articles_org_id", table_name="help_articles")
    op.drop_table("help_articles")

    op.drop_index("ix_help_categories_org_published", table_name="help_categories")
    op.drop_index("ix_help_categories_org_slug", table_name="help_categories")
    op.drop_index("ix_help_categories_is_published", table_name="help_categories")
    op.drop_index("ix_help_categories_org_id", table_name="help_categories")
    op.drop_table("help_categories")

    op.drop_index("ix_demo_scenarios_org_active", table_name="demo_scenarios")
    op.drop_index("ix_demo_scenarios_org_key", table_name="demo_scenarios")
    op.drop_index("ix_demo_scenarios_org_id", table_name="demo_scenarios")
    op.drop_table("demo_scenarios")

    op.drop_index("ix_org_plan_entitlements_org_current", table_name="org_plan_entitlements")
    op.drop_index("ix_org_plan_entitlements_org_id", table_name="org_plan_entitlements")
    op.drop_table("org_plan_entitlements")
