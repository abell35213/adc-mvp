"""add retry parent link to exports

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exports",
        sa.Column("retry_parent_export_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_exports_retry_parent_export_id",
        "exports",
        "exports",
        ["retry_parent_export_id"],
        ["export_id"],
    )
    op.create_index(
        "ix_exports_retry_parent_export_id",
        "exports",
        ["retry_parent_export_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_exports_retry_parent_export_id", table_name="exports")
    op.drop_constraint("fk_exports_retry_parent_export_id", "exports", type_="foreignkey")
    op.drop_column("exports", "retry_parent_export_id")
