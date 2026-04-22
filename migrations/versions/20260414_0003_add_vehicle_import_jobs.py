"""Add organization vehicle registry and async vehicle import jobs.

Revision ID: 20260414_0003
Revises: 20260411_0002
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260414_0003"
down_revision = "20260411_0002"
branch_labels = None
depends_on = None


vehicle_import_job_status = sa.Enum(
    "pending",
    "running",
    "succeeded",
    "failed",
    name="vehicle_import_job_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    vehicle_import_job_status.create(bind, checkfirst=True)

    op.create_table(
        "org_vehicle_registry",
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_number", sa.Text(), nullable=False),
        sa.Column("vin", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("provider_vehicle_id", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("vehicle_id"),
    )
    op.create_index("ix_org_vehicle_registry_org_id", "org_vehicle_registry", ["org_id"])
    op.create_index(
        "ix_org_vehicle_registry_org_unit",
        "org_vehicle_registry",
        ["org_id", "unit_number"],
        unique=True,
    )
    op.create_index(
        "ix_org_vehicle_registry_org_provider_ext",
        "org_vehicle_registry",
        ["org_id", "provider", "provider_vehicle_id"],
    )

    op.create_table(
        "vehicle_import_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("status", vehicle_import_job_status, nullable=False, server_default="pending"),
        sa.Column("records_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_errored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("outcomes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_vehicle_import_jobs_org_id", "vehicle_import_jobs", ["org_id"])
    op.create_index("ix_vehicle_import_jobs_status", "vehicle_import_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_vehicle_import_jobs_status", table_name="vehicle_import_jobs")
    op.drop_index("ix_vehicle_import_jobs_org_id", table_name="vehicle_import_jobs")
    op.drop_table("vehicle_import_jobs")

    op.drop_index("ix_org_vehicle_registry_org_provider_ext", table_name="org_vehicle_registry")
    op.drop_index("ix_org_vehicle_registry_org_unit", table_name="org_vehicle_registry")
    op.drop_index("ix_org_vehicle_registry_org_id", table_name="org_vehicle_registry")
    op.drop_table("org_vehicle_registry")

    vehicle_import_job_status.drop(op.get_bind(), checkfirst=True)
