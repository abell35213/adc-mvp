"""add org export validation runs table

Revision ID: 0024_add_org_export_validation_runs
Revises: 0023_add_org_test_incident_runs
Create Date: 2026-04-15 00:00:00.000000
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    org_export_validation_run_status = sa.Enum(
        "passed",
        "failed",
        name="org_export_validation_run_status",
    )
    org_export_validation_run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "org_export_validation_runs",
        sa.Column("validation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("export_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", org_export_validation_run_status, nullable=False, server_default="failed"),
        sa.Column("results_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("warnings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("missing_items_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("validated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["export_id"], ["exports.export_id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("validation_run_id"),
    )
    op.create_index(
        "ix_org_export_validation_runs_org_id",
        "org_export_validation_runs",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_export_validation_runs_incident_id",
        "org_export_validation_runs",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_export_validation_runs_export_id",
        "org_export_validation_runs",
        ["export_id"],
        unique=False,
    )
    op.create_index(
        "ix_org_export_validation_runs_status",
        "org_export_validation_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_org_export_validation_runs_validated_at_utc",
        "org_export_validation_runs",
        ["validated_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_org_export_validation_runs_org_validated",
        "org_export_validation_runs",
        ["org_id", "validated_at_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_export_validation_runs_org_validated",
        table_name="org_export_validation_runs",
    )
    op.drop_index(
        "ix_org_export_validation_runs_validated_at_utc",
        table_name="org_export_validation_runs",
    )
    op.drop_index(
        "ix_org_export_validation_runs_status",
        table_name="org_export_validation_runs",
    )
    op.drop_index(
        "ix_org_export_validation_runs_export_id",
        table_name="org_export_validation_runs",
    )
    op.drop_index(
        "ix_org_export_validation_runs_incident_id",
        table_name="org_export_validation_runs",
    )
    op.drop_index(
        "ix_org_export_validation_runs_org_id",
        table_name="org_export_validation_runs",
    )
    op.drop_table("org_export_validation_runs")

    org_export_validation_run_status = sa.Enum(
        "passed",
        "failed",
        name="org_export_validation_run_status",
    )
    org_export_validation_run_status.drop(op.get_bind(), checkfirst=True)
