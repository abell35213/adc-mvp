"""add org user invites table

Revision ID: 0021_add_org_user_invites_table
Revises: 0020_add_org_settings_and_onboarding_completion
Create Date: 2026-04-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Union


# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "org_user_invites",
        sa.Column("invite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'safety_manager'"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_sent_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deactivated_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("invite_id"),
    )
    op.create_index("ix_org_user_invites_org_id", "org_user_invites", ["org_id"])
    op.create_index("ix_org_user_invites_email", "org_user_invites", ["email"])
    op.create_index("ix_org_user_invites_status", "org_user_invites", ["status"])


def downgrade() -> None:
    op.drop_index("ix_org_user_invites_status", table_name="org_user_invites")
    op.drop_index("ix_org_user_invites_email", table_name="org_user_invites")
    op.drop_index("ix_org_user_invites_org_id", table_name="org_user_invites")
    op.drop_table("org_user_invites")
