"""add case note type and tags columns

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


case_note_type = sa.Enum("standard", "tagged", "decision", name="case_note_type")


def upgrade() -> None:
    bind = op.get_bind()
    case_note_type.create(bind, checkfirst=True)

    op.add_column(
        "case_notes",
        sa.Column("note_type", case_note_type, nullable=True, server_default="standard"),
    )
    op.add_column(
        "case_notes",
        sa.Column(
            "tags_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.execute("UPDATE case_notes SET note_type = 'standard' WHERE note_type IS NULL")
    op.execute("UPDATE case_notes SET tags_json = '[]'::jsonb WHERE tags_json IS NULL")

    op.alter_column("case_notes", "note_type", nullable=False)
    op.alter_column("case_notes", "tags_json", nullable=False)


def downgrade() -> None:
    op.drop_column("case_notes", "tags_json")
    op.drop_column("case_notes", "note_type")

    bind = op.get_bind()
    case_note_type.drop(bind, checkfirst=True)
