"""add org test incident runs and test incident flag

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-15 00:00:00.000000
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


org_test_incident_run_status = sa.Enum(
    "not_started",
    "in_progress",
    "completed",
    "blocked",
    name="org_test_incident_run_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    org_test_incident_run_status.create(bind, checkfirst=True)

    op.add_column(
        "incidents",
        sa.Column(
            "is_test_incident",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_incidents_is_test_incident",
        "incidents",
        ["is_test_incident"],
        unique=False,
    )

    op.create_table(
        "org_test_incident_runs",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            org_test_incident_run_status,
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column(
            "step_results_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "findings_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_org_test_incident_runs_org_id",
        "org_test_incident_runs",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_test_incident_runs_incident_id",
        "org_test_incident_runs",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_test_incident_runs_org_started",
        "org_test_incident_runs",
        ["org_id", "started_at_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_test_incident_runs_org_started",
        table_name="org_test_incident_runs",
    )
    op.drop_index(
        "ix_org_test_incident_runs_incident_id",
        table_name="org_test_incident_runs",
    )
    op.drop_index("ix_org_test_incident_runs_org_id", table_name="org_test_incident_runs")
    op.drop_table("org_test_incident_runs")

    op.drop_index("ix_incidents_is_test_incident", table_name="incidents")
    op.drop_column("incidents", "is_test_incident")

    bind = op.get_bind()
    org_test_incident_run_status.drop(bind, checkfirst=True)
