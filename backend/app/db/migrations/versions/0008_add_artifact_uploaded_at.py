"""add uploaded timestamp to artifacts

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("uploaded_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "uploaded_at_utc")
