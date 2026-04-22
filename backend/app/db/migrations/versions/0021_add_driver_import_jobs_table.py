"""add driver import jobs table

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


driver_import_job_status = sa.Enum(
    "pending",
    "running",
    "succeeded",
    "failed",
    name="driver_import_job_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    driver_import_job_status.create(bind, checkfirst=True)

    op.create_table(
        "driver_import_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column(
            "status",
            driver_import_job_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("records_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "records_processed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_errored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "warnings_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "outcomes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "completed_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True
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
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )

    op.create_index(
        "ix_driver_import_jobs_org_id", "driver_import_jobs", ["org_id"], unique=False
    )
    op.create_index(
        "ix_driver_import_jobs_status", "driver_import_jobs", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_driver_import_jobs_status", table_name="driver_import_jobs")
    op.drop_index("ix_driver_import_jobs_org_id", table_name="driver_import_jobs")
    op.drop_table("driver_import_jobs")

    bind = op.get_bind()
    driver_import_job_status.drop(bind, checkfirst=True)
