"""expand message operations for delivery reliability

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("message_operations", sa.Column("purpose", sa.Text(), nullable=False, server_default="notification"))
    op.add_column("message_operations", sa.Column("to_e164", sa.Text(), nullable=True))
    op.add_column("message_operations", sa.Column("provider_message_id", sa.Text(), nullable=True))
    op.add_column("message_operations", sa.Column("normalized_error_code", sa.Text(), nullable=True))

    op.create_index("ix_message_operations_purpose", "message_operations", ["purpose"], unique=False)
    op.create_index("ix_message_operations_to_e164", "message_operations", ["to_e164"], unique=False)
    op.create_index("ix_message_operations_provider_message_id", "message_operations", ["provider_message_id"], unique=False)
    op.create_index("ix_message_operations_normalized_error_code", "message_operations", ["normalized_error_code"], unique=False)

    op.execute("ALTER TYPE message_operation_status ADD VALUE IF NOT EXISTS 'undelivered'")

    op.create_table(
        "message_operation_status_history",
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("normalized_error_code", sa.Text(), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["message_operation_id"], ["message_operations.message_operation_id"]),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index("ix_message_operation_status_history_message_operation_id", "message_operation_status_history", ["message_operation_id"], unique=False)
    op.create_index("ix_message_operation_status_history_to_status", "message_operation_status_history", ["to_status"], unique=False)
    op.create_index("ix_message_operation_status_history_provider_message_id", "message_operation_status_history", ["provider_message_id"], unique=False)
    op.create_index("ix_message_operation_status_history_normalized_error_code", "message_operation_status_history", ["normalized_error_code"], unique=False)
    op.create_index("ix_message_operation_status_history_created_at_utc", "message_operation_status_history", ["created_at_utc"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_message_operation_status_history_created_at_utc", table_name="message_operation_status_history")
    op.drop_index("ix_message_operation_status_history_normalized_error_code", table_name="message_operation_status_history")
    op.drop_index("ix_message_operation_status_history_provider_message_id", table_name="message_operation_status_history")
    op.drop_index("ix_message_operation_status_history_to_status", table_name="message_operation_status_history")
    op.drop_index("ix_message_operation_status_history_message_operation_id", table_name="message_operation_status_history")
    op.drop_table("message_operation_status_history")

    op.drop_index("ix_message_operations_normalized_error_code", table_name="message_operations")
    op.drop_index("ix_message_operations_provider_message_id", table_name="message_operations")
    op.drop_index("ix_message_operations_to_e164", table_name="message_operations")
    op.drop_index("ix_message_operations_purpose", table_name="message_operations")

    op.drop_column("message_operations", "normalized_error_code")
    op.drop_column("message_operations", "provider_message_id")
    op.drop_column("message_operations", "to_e164")
    op.drop_column("message_operations", "purpose")
