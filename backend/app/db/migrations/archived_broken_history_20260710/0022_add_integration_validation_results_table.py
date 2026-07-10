"""add integration validation results table

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-14 00:00:00.000000
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "integration_validation_results",
        sa.Column(
            "validation_result_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("credential_status", sa.Text(), nullable=False),
        sa.Column("capability_status", sa.Text(), nullable=False),
        sa.Column("mapping_status", sa.Text(), nullable=False),
        sa.Column(
            "messages_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "validated_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["integration_connections.connection_id"]
        ),
    )
    op.create_index(
        "ix_integration_validation_results_org_id",
        "integration_validation_results",
        ["org_id"],
    )
    op.create_index(
        "ix_integration_validation_results_connection_id",
        "integration_validation_results",
        ["connection_id"],
    )
    op.create_index(
        "ix_integration_validation_results_validated_at_utc",
        "integration_validation_results",
        ["validated_at_utc"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_validation_results_validated_at_utc",
        table_name="integration_validation_results",
    )
    op.drop_index(
        "ix_integration_validation_results_connection_id",
        table_name="integration_validation_results",
    )
    op.drop_index(
        "ix_integration_validation_results_org_id",
        table_name="integration_validation_results",
    )
    op.drop_table("integration_validation_results")
