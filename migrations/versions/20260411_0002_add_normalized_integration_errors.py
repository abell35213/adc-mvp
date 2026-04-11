"""Add normalized integration error columns.

Revision ID: 20260411_0002
Revises: 20260411_0001
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0002"
down_revision = "20260411_0001"
branch_labels = None
depends_on = None


def _add_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("error_code", sa.Text(), nullable=True))
    op.add_column(table_name, sa.Column("error_category", sa.Text(), nullable=True))
    op.add_column(table_name, sa.Column("error_provider_key", sa.Text(), nullable=True))
    op.add_column(table_name, sa.Column("error_retryable", sa.Boolean(), nullable=True))
    op.add_column(table_name, sa.Column("error_user_facing_message", sa.Text(), nullable=True))
    op.add_column(table_name, sa.Column("error_operator_message", sa.Text(), nullable=True))


def _drop_columns(table_name: str) -> None:
    op.drop_column(table_name, "error_operator_message")
    op.drop_column(table_name, "error_user_facing_message")
    op.drop_column(table_name, "error_retryable")
    op.drop_column(table_name, "error_provider_key")
    op.drop_column(table_name, "error_category")
    op.drop_column(table_name, "error_code")


def upgrade() -> None:
    _add_columns("integration_operations")
    _add_columns("evidence_requests")

    op.create_index(
        "ix_integration_operations_error_code",
        "integration_operations",
        ["error_code"],
    )
    op.create_index(
        "ix_integration_operations_error_category",
        "integration_operations",
        ["error_category"],
    )
    op.create_index(
        "ix_integration_operations_error_provider_key",
        "integration_operations",
        ["error_provider_key"],
    )

    op.create_index("ix_evidence_requests_error_code", "evidence_requests", ["error_code"])
    op.create_index(
        "ix_evidence_requests_error_category", "evidence_requests", ["error_category"]
    )
    op.create_index(
        "ix_evidence_requests_error_provider_key",
        "evidence_requests",
        ["error_provider_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_requests_error_provider_key", table_name="evidence_requests")
    op.drop_index("ix_evidence_requests_error_category", table_name="evidence_requests")
    op.drop_index("ix_evidence_requests_error_code", table_name="evidence_requests")

    op.drop_index(
        "ix_integration_operations_error_provider_key",
        table_name="integration_operations",
    )
    op.drop_index("ix_integration_operations_error_category", table_name="integration_operations")
    op.drop_index("ix_integration_operations_error_code", table_name="integration_operations")

    _drop_columns("evidence_requests")
    _drop_columns("integration_operations")
