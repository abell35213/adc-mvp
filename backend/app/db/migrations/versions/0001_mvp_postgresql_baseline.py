"""mvp postgresql baseline

Revision ID: 0001
Revises: 
Create Date: 2026-07-10

This pre-production baseline replaces the incomplete historical migration chain.
The archived chain is retained under app/db/migrations/archived_broken_history_20260710
for audit/reference, outside Alembic's active versions directory.
"""

from typing import Sequence, Union

from alembic import op

from app.db.models import Base


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=False)
