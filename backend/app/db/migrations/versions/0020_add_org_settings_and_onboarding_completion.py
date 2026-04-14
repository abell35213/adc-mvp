"""add org settings fields and onboarding step completion table

Revision ID: 0020_add_org_settings_and_onboarding_completion
Revises: 0019_add_onboarding_readiness_snapshot_tables
Create Date: 2026-04-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0020_add_org_settings_and_onboarding_completion"
down_revision = "0019_add_onboarding_readiness_snapshot_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("legal_name", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("display_name", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("timezone", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("region", sa.Text(), nullable=True))
    op.add_column(
        "orgs",
        sa.Column(
            "contacts_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "orgs",
        sa.Column(
            "implementation_contact_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column("orgs", sa.Column("logo_url", sa.Text(), nullable=True))

    op.create_table(
        "org_onboarding_step_completions",
        sa.Column("completion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_key", sa.Text(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completion_source", sa.Text(), nullable=True),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("completion_id"),
    )
    op.create_index(
        "ix_org_onboarding_step_completions_org_id",
        "org_onboarding_step_completions",
        ["org_id"],
    )
    op.create_index(
        "ix_org_onboarding_step_completion_org_step",
        "org_onboarding_step_completions",
        ["org_id", "step_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_onboarding_step_completion_org_step",
        table_name="org_onboarding_step_completions",
    )
    op.drop_index(
        "ix_org_onboarding_step_completions_org_id",
        table_name="org_onboarding_step_completions",
    )
    op.drop_table("org_onboarding_step_completions")

    op.drop_column("orgs", "logo_url")
    op.drop_column("orgs", "implementation_contact_json")
    op.drop_column("orgs", "contacts_json")
    op.drop_column("orgs", "region")
    op.drop_column("orgs", "timezone")
    op.drop_column("orgs", "display_name")
    op.drop_column("orgs", "legal_name")
