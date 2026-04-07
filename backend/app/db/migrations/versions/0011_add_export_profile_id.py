"""add profile id to exports

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exports",
        sa.Column("profile_id", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE exports
        SET profile_id = CASE export_type
            WHEN 'court_defense' THEN 'court_defense_v1'
            WHEN 'insurer_packet' THEN 'insurer_packet_v1'
            WHEN 'internal_review' THEN 'internal_review_v1'
            WHEN 'compliance_audit' THEN 'compliance_audit_v1'
            ELSE 'court_defense_v1'
        END
        """
    )
    op.alter_column("exports", "profile_id", nullable=False, server_default="court_defense_v1")


def downgrade() -> None:
    op.drop_column("exports", "profile_id")
