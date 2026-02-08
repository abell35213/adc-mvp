"""add auth tables and org_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- orgs ---
    op.create_table(
        "orgs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="safety_manager"),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- user_orgs ---
    op.create_table(
        "user_orgs",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orgs.id"),
            primary_key=True,
        ),
    )

    # --- incidents.org_id ---
    op.add_column(
        "incidents",
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True),
    )
    op.create_index("ix_incidents_org_id", "incidents", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_org_id", table_name="incidents")
    op.drop_column("incidents", "org_id")
    op.drop_table("user_orgs")
    op.drop_table("users")
    op.drop_table("orgs")
