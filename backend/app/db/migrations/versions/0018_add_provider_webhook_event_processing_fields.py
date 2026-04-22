"""add provider webhook event processing fields

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-22

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


def upgrade() -> None:
    op.add_column("provider_webhook_events", sa.Column("signature_valid", sa.Boolean(), nullable=True))
    op.add_column("provider_webhook_events", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column("provider_webhook_events", sa.Column("processing_outcome", sa.Text(), nullable=True))
    op.add_column(
        "provider_webhook_events",
        sa.Column("raw_payload", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "provider_webhook_events",
        sa.Column(
            "error_details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_index(
        "ix_provider_webhook_events_signature_valid",
        "provider_webhook_events",
        ["signature_valid"],
        unique=False,
    )
    op.create_index(
        "ix_provider_webhook_events_idempotency_key",
        "provider_webhook_events",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        "ix_provider_webhook_events_processing_outcome",
        "provider_webhook_events",
        ["processing_outcome"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_webhook_events_processing_outcome", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_idempotency_key", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_signature_valid", table_name="provider_webhook_events")

    op.drop_column("provider_webhook_events", "error_details_json")
    op.drop_column("provider_webhook_events", "raw_payload")
    op.drop_column("provider_webhook_events", "processing_outcome")
    op.drop_column("provider_webhook_events", "idempotency_key")
    op.drop_column("provider_webhook_events", "signature_valid")
