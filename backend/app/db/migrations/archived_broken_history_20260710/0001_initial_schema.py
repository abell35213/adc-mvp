"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-02-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- events (append-only; source of truth) ---
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
    )
    op.create_index("ix_events_incident_id", "events", ["incident_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_occurred_at_utc", "events", ["occurred_at_utc"])

    # --- incidents (summary pointer) ---
    op.create_table(
        "incidents",
        sa.Column("incident_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=True),
        sa.Column("samsara_vehicle_id", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=True),
    )

    # --- artifacts (metadata lookup) ---
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("capture_window_start_utc", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("capture_window_end_utc", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("s3_bucket", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("unavailable_reason_code", sa.Text(), nullable=True),
        sa.Column("unavailable_reason_detail", sa.Text(), nullable=True),
    )
    op.create_index("ix_artifacts_incident_id", "artifacts", ["incident_id"])

    # --- exports ---
    op.create_table(
        "exports",
        sa.Column("export_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("s3_bucket", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_exports_incident_id", "exports", ["incident_id"])


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("artifacts")
    op.drop_table("incidents")
    op.drop_table("events")
