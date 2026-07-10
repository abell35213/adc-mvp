"""add case management tables and incident workflow fields

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


incident_case_status = sa.Enum(
    "new",
    "in_review",
    "awaiting_evidence",
    "awaiting_follow_up",
    "ready_for_export",
    "exported",
    "escalated",
    "closed",
    name="incident_case_status",
)

case_task_type = sa.Enum(
    "review",
    "evidence",
    "follow_up",
    "export",
    "other",
    name="case_task_type",
)

case_task_status = sa.Enum(
    "open",
    "in_progress",
    "blocked",
    "completed",
    "canceled",
    name="case_task_status",
)

case_task_priority = sa.Enum(
    "low",
    "medium",
    "high",
    "urgent",
    name="case_task_priority",
)


def upgrade() -> None:
    bind = op.get_bind()
    incident_case_status.create(bind, checkfirst=True)
    case_task_type.create(bind, checkfirst=True)
    case_task_status.create(bind, checkfirst=True)
    case_task_priority.create(bind, checkfirst=True)

    op.add_column(
        "incidents",
        sa.Column("case_status", incident_case_status, nullable=False, server_default="new"),
    )
    op.add_column("incidents", sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("incidents", sa.Column("owner_assigned_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "incidents",
        sa.Column("owner_assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("incidents", sa.Column("team_queue", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("readiness_state", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("completeness_percent", sa.Integer(), nullable=True))
    op.add_column("incidents", sa.Column("completeness_status", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("first_reviewed_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("last_activity_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("ready_for_export_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "incidents",
        sa.Column(
            "updated_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_foreign_key("fk_incidents_owner_user_id", "incidents", "users", ["owner_user_id"], ["id"])
    op.create_foreign_key(
        "fk_incidents_owner_assigned_by_user_id",
        "incidents",
        "users",
        ["owner_assigned_by_user_id"],
        ["id"],
    )

    op.create_index("ix_incidents_org_case_status_owner", "incidents", ["org_id", "case_status", "owner_user_id"], unique=False)
    op.create_index("ix_incidents_org_readiness_state", "incidents", ["org_id", "readiness_state"], unique=False)
    op.create_index("ix_incidents_org_updated_at_utc", "incidents", ["org_id", "updated_at_utc"], unique=False)
    op.create_index("ix_incidents_org_last_activity_at_utc", "incidents", ["org_id", "last_activity_at_utc"], unique=False)

    op.create_table(
        "case_notes",
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("edited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("edited_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["edited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("note_id"),
    )
    op.create_index("ix_case_notes_incident_id", "case_notes", ["incident_id"], unique=False)
    op.create_index("ix_case_notes_org_id", "case_notes", ["org_id"], unique=False)
    op.create_index("ix_case_notes_org_incident_created", "case_notes", ["org_id", "incident_id", "created_at_utc"], unique=False)
    op.create_index(
        "ix_case_notes_org_incident_deleted_created",
        "case_notes",
        ["org_id", "incident_id", "is_deleted", "created_at_utc"],
        unique=False,
    )

    op.create_table(
        "case_tasks",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", case_task_type, nullable=False, server_default="other"),
        sa.Column("status", case_task_status, nullable=False, server_default="open"),
        sa.Column("priority", case_task_priority, nullable=False, server_default="medium"),
        sa.Column("due_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canceled_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canceled_reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["canceled_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_case_tasks_incident_id", "case_tasks", ["incident_id"], unique=False)
    op.create_index("ix_case_tasks_org_id", "case_tasks", ["org_id"], unique=False)
    op.create_index("ix_case_tasks_org_incident_status", "case_tasks", ["org_id", "incident_id", "status"], unique=False)
    op.create_index("ix_case_tasks_org_status_due_at_utc", "case_tasks", ["org_id", "status", "due_at_utc"], unique=False)

    op.create_table(
        "case_readiness_overrides",
        sa.Column("override_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("readiness_state", sa.Text(), nullable=True),
        sa.Column("completeness_percent", sa.Integer(), nullable=True),
        sa.Column("completeness_status", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cleared_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cleared_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cleared_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("override_id"),
    )
    op.create_index("ix_case_readiness_overrides_incident_id", "case_readiness_overrides", ["incident_id"], unique=False)
    op.create_index("ix_case_readiness_overrides_org_id", "case_readiness_overrides", ["org_id"], unique=False)
    op.create_index(
        "ix_case_readiness_overrides_org_incident_created",
        "case_readiness_overrides",
        ["org_id", "incident_id", "created_at_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_case_readiness_overrides_org_incident_created", table_name="case_readiness_overrides")
    op.drop_index("ix_case_readiness_overrides_org_id", table_name="case_readiness_overrides")
    op.drop_index("ix_case_readiness_overrides_incident_id", table_name="case_readiness_overrides")
    op.drop_table("case_readiness_overrides")

    op.drop_index("ix_case_tasks_org_status_due_at_utc", table_name="case_tasks")
    op.drop_index("ix_case_tasks_org_incident_status", table_name="case_tasks")
    op.drop_index("ix_case_tasks_org_id", table_name="case_tasks")
    op.drop_index("ix_case_tasks_incident_id", table_name="case_tasks")
    op.drop_table("case_tasks")

    op.drop_index("ix_case_notes_org_incident_deleted_created", table_name="case_notes")
    op.drop_index("ix_case_notes_org_incident_created", table_name="case_notes")
    op.drop_index("ix_case_notes_org_id", table_name="case_notes")
    op.drop_index("ix_case_notes_incident_id", table_name="case_notes")
    op.drop_table("case_notes")

    op.drop_index("ix_incidents_org_last_activity_at_utc", table_name="incidents")
    op.drop_index("ix_incidents_org_updated_at_utc", table_name="incidents")
    op.drop_index("ix_incidents_org_readiness_state", table_name="incidents")
    op.drop_index("ix_incidents_org_case_status_owner", table_name="incidents")
    op.drop_constraint("fk_incidents_owner_assigned_by_user_id", "incidents", type_="foreignkey")
    op.drop_constraint("fk_incidents_owner_user_id", "incidents", type_="foreignkey")

    op.drop_column("incidents", "updated_at_utc")
    op.drop_column("incidents", "ready_for_export_at_utc")
    op.drop_column("incidents", "last_activity_at_utc")
    op.drop_column("incidents", "first_reviewed_at_utc")
    op.drop_column("incidents", "completeness_status")
    op.drop_column("incidents", "completeness_percent")
    op.drop_column("incidents", "readiness_state")
    op.drop_column("incidents", "team_queue")
    op.drop_column("incidents", "owner_assigned_by_user_id")
    op.drop_column("incidents", "owner_assigned_at_utc")
    op.drop_column("incidents", "owner_user_id")
    op.drop_column("incidents", "case_status")

    bind = op.get_bind()
    case_task_priority.drop(bind, checkfirst=True)
    case_task_status.drop(bind, checkfirst=True)
    case_task_type.drop(bind, checkfirst=True)
    incident_case_status.drop(bind, checkfirst=True)
