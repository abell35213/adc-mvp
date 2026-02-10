"""add instruction_source to orgs

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orgs",
        sa.Column(
            "instruction_source",
            sa.Text(),
            nullable=False,
            server_default="default",
        ),
    )


def downgrade() -> None:
    op.drop_column("orgs", "instruction_source")
