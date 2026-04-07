"""add mfa enrollment metadata and audit event indexes

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MFA_AUDIT_EVENT_TYPES = (
    "mfa_enrollment_completed",
    "mfa_challenge_completed",
    "mfa_disabled",
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("mfa_secret_hash", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("mfa_enrolled_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("mfa_last_challenged_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("mfa_disabled_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.alter_column("users", "mfa_enabled", server_default=None)

    op.add_column(
        "orgs",
        sa.Column(
            "require_org_admin_mfa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("orgs", "require_org_admin_mfa", server_default=None)

    op.create_index(
        "ix_events_mfa_audit",
        "events",
        ["org_id", "event_type", "occurred_at_utc"],
        unique=False,
        postgresql_where=sa.text(
            "event_type IN ('mfa_enrollment_completed', 'mfa_challenge_completed', 'mfa_disabled')"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_events_mfa_audit", table_name="events")
    op.drop_column("orgs", "require_org_admin_mfa")
    op.drop_column("users", "mfa_disabled_at_utc")
    op.drop_column("users", "mfa_last_challenged_at_utc")
    op.drop_column("users", "mfa_enrolled_at_utc")
    op.drop_column("users", "mfa_secret_hash")
    op.drop_column("users", "mfa_enabled")
