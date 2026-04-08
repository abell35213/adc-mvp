"""add job execution metadata table

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_execution_status = sa.Enum(
        "queued",
        "running",
        "retrying",
        "failed",
        "succeeded",
        "stuck",
        name="job_execution_status",
    )
    job_execution_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "job_execution_meta",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("celery_task_id", sa.Text(), nullable=False),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column(
            "status",
            job_execution_status,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=True),
        sa.Column("retry_category", sa.Text(), nullable=True),
        sa.Column("should_retry", sa.Boolean(), nullable=True),
        sa.Column(
            "next_retry_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("started_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "finished_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "last_heartbeat_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "args_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "kwargs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("celery_task_id"),
    )

    op.create_index(
        "ix_job_execution_meta_celery_task_id",
        "job_execution_meta",
        ["celery_task_id"],
        unique=True,
    )
    op.create_index(
        "ix_job_execution_meta_task_name",
        "job_execution_meta",
        ["task_name"],
        unique=False,
    )
    op.create_index(
        "ix_job_execution_meta_task_type",
        "job_execution_meta",
        ["task_type"],
        unique=False,
    )
    op.create_index(
        "ix_job_execution_meta_status", "job_execution_meta", ["status"], unique=False
    )
    op.create_index(
        "ix_job_execution_meta_retry_category",
        "job_execution_meta",
        ["retry_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_job_execution_meta_retry_category", table_name="job_execution_meta"
    )
    op.drop_index("ix_job_execution_meta_status", table_name="job_execution_meta")
    op.drop_index("ix_job_execution_meta_task_type", table_name="job_execution_meta")
    op.drop_index("ix_job_execution_meta_task_name", table_name="job_execution_meta")
    op.drop_index(
        "ix_job_execution_meta_celery_task_id", table_name="job_execution_meta"
    )
    op.drop_table("job_execution_meta")

    job_execution_status = sa.Enum(
        "queued",
        "running",
        "retrying",
        "failed",
        "succeeded",
        "stuck",
        name="job_execution_status",
    )
    job_execution_status.drop(op.get_bind(), checkfirst=True)
