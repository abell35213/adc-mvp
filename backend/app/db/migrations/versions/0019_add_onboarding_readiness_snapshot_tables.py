"""add onboarding readiness snapshot tables

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-14

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


org_launch_readiness_status = sa.Enum(
    "not_started",
    "in_progress",
    "pilot_ready",
    "launch_ready",
    "blocked",
    name="org_launch_readiness_status",
)

org_launch_readiness_step_status = sa.Enum(
    "not_started",
    "in_progress",
    "completed",
    "blocked",
    name="org_launch_readiness_step_status",
)

org_launch_readiness_blocker_severity = sa.Enum(
    "info",
    "warning",
    "error",
    name="org_launch_readiness_blocker_severity",
)


def upgrade() -> None:
    bind = op.get_bind()
    org_launch_readiness_status.create(bind, checkfirst=True)
    org_launch_readiness_step_status.create(bind, checkfirst=True)
    org_launch_readiness_blocker_severity.create(bind, checkfirst=True)

    op.create_table(
        "org_launch_readiness_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            org_launch_readiness_status,
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("percent_complete", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_org_launch_readiness_snapshots_org_id",
        "org_launch_readiness_snapshots",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_launch_readiness_snapshots_org_created",
        "org_launch_readiness_snapshots",
        ["org_id", "created_at_utc"],
        unique=False,
    )

    op.create_table(
        "org_launch_readiness_step_progress",
        sa.Column("step_progress_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_key", sa.Text(), nullable=False),
        sa.Column("step_label", sa.Text(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            org_launch_readiness_step_status,
            nullable=False,
            server_default="not_started",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "completed_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "updated_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["org_launch_readiness_snapshots.snapshot_id"]
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("step_progress_id"),
    )
    op.create_index(
        "ix_org_launch_readiness_step_progress_org_id",
        "org_launch_readiness_step_progress",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_launch_readiness_step_progress_snapshot_id",
        "org_launch_readiness_step_progress",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_launch_readiness_steps_org_snapshot",
        "org_launch_readiness_step_progress",
        ["org_id", "snapshot_id", "step_order"],
        unique=False,
    )

    op.create_table(
        "org_launch_readiness_blockers",
        sa.Column("blocker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            org_launch_readiness_blocker_severity,
            nullable=False,
            server_default="warning",
        ),
        sa.Column("blocking_step_key", sa.Text(), nullable=True),
        sa.Column(
            "is_resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "resolved_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["org_launch_readiness_snapshots.snapshot_id"]
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("blocker_id"),
    )
    op.create_index(
        "ix_org_launch_readiness_blockers_org_id",
        "org_launch_readiness_blockers",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_launch_readiness_blockers_snapshot_id",
        "org_launch_readiness_blockers",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_launch_readiness_blockers_org_snapshot",
        "org_launch_readiness_blockers",
        ["org_id", "snapshot_id", "is_resolved"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_launch_readiness_blockers_org_snapshot",
        table_name="org_launch_readiness_blockers",
    )
    op.drop_index(
        "ix_org_launch_readiness_blockers_snapshot_id",
        table_name="org_launch_readiness_blockers",
    )
    op.drop_index(
        "ix_org_launch_readiness_blockers_org_id",
        table_name="org_launch_readiness_blockers",
    )
    op.drop_table("org_launch_readiness_blockers")

    op.drop_index(
        "ix_org_launch_readiness_steps_org_snapshot",
        table_name="org_launch_readiness_step_progress",
    )
    op.drop_index(
        "ix_org_launch_readiness_step_progress_snapshot_id",
        table_name="org_launch_readiness_step_progress",
    )
    op.drop_index(
        "ix_org_launch_readiness_step_progress_org_id",
        table_name="org_launch_readiness_step_progress",
    )
    op.drop_table("org_launch_readiness_step_progress")

    op.drop_index(
        "ix_org_launch_readiness_snapshots_org_created",
        table_name="org_launch_readiness_snapshots",
    )
    op.drop_index(
        "ix_org_launch_readiness_snapshots_org_id",
        table_name="org_launch_readiness_snapshots",
    )
    op.drop_table("org_launch_readiness_snapshots")

    bind = op.get_bind()
    org_launch_readiness_blocker_severity.drop(bind, checkfirst=True)
    org_launch_readiness_step_status.drop(bind, checkfirst=True)
    org_launch_readiness_status.drop(bind, checkfirst=True)
