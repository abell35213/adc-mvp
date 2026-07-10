"""add otp code hash to otp challenges

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "otp_challenges",
        sa.Column(
            "otp_code_hash",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.alter_column("otp_challenges", "otp_code_hash", server_default=None)


def downgrade() -> None:
    op.drop_column("otp_challenges", "otp_code_hash")
