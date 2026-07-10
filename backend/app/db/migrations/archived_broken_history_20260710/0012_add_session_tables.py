"""add session tables and refresh lineage

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=True),
        sa.Column("client_type", sa.Text(), nullable=False),
        sa.Column("device_descriptor", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("refresh_family_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_org_id", "sessions", ["org_id"])
    op.create_index("ix_sessions_refresh_family_id", "sessions", ["refresh_family_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("parent_token_id", UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("issued_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consumed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["parent_token_id"], ["refresh_tokens.token_id"]),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index("ix_refresh_tokens_refresh_family_id", "refresh_tokens", ["refresh_family_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_refresh_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_sessions_refresh_family_id", table_name="sessions")
    op.drop_index("ix_sessions_org_id", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
