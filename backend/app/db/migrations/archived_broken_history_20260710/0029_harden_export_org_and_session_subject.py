"""Harden Export.org_id (NOT NULL) and add Session.subject_id.

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-24 00:00:00.000000

This migration tightens two long-standing data-integrity issues identified during
the Q2 2026 code review:

* ``exports.org_id`` was nullable. The download authorization helper already
  null-checks the value, but defense-in-depth requires the column to be
  ``NOT NULL`` and to be populated for every existing row from the parent
  incident. Any export still missing an ``org_id`` is backfilled from
  ``incidents.org_id`` before the constraint is applied.

* ``sessions`` had no way to record the subject of a non-user session (i.e.
  driver sessions where ``user_id`` is intentionally ``NULL``). This made it
  impossible to issue a correctly-scoped access token on refresh. A new nullable
  ``subject_id`` column is added so the session can carry the driver UUID
  (or any future non-user actor) without overloading ``user_id``.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # --- exports.org_id: backfill, then enforce NOT NULL ----------------------------
    bind = op.get_bind()
    # Backfill any existing exports whose org_id is null using the parent incident's
    # org_id. This is a no-op when the table is empty (e.g. fresh install).
    bind.execute(
        sa.text(
            """
            UPDATE exports
               SET org_id = incidents.org_id
              FROM incidents
             WHERE exports.org_id IS NULL
               AND incidents.incident_id = exports.incident_id
            """
        )
    )
    op.alter_column(
        "exports",
        "org_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # --- sessions.subject_id: new nullable UUID column -------------------------------
    op.add_column(
        "sessions",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_sessions_subject_id", "sessions", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_subject_id", table_name="sessions")
    op.drop_column("sessions", "subject_id")
    op.alter_column(
        "exports",
        "org_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
