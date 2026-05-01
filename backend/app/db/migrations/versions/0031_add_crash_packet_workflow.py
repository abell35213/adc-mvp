"""add crash packet workflow tables

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-01 00:00:00.000000

Adds the Phase-1 tables for the 15-minute crash notification packet:

- ``org_notification_recipients`` — per-org control file of recipients.
- ``crash_packet_deliveries`` — one row per dispatch attempt for an incident,
  used for idempotency and SLA tracking.

Also extends the ``incident_status`` enum with the ``accident_occurred`` value
which is the trigger for the crash packet workflow.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. Extend the incident_status enum with `accident_occurred`.
    if is_pg:
        op.execute("ALTER TYPE incident_status ADD VALUE IF NOT EXISTS 'accident_occurred'")

    # 2. org_notification_recipients
    op.create_table(
        "org_notification_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("role_tag", sa.Text(), nullable=True),
        sa.Column(
            "channels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"email\"]'"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["orgs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_notification_recipients_org_id",
        "org_notification_recipients",
        ["org_id"],
    )
    op.create_index(
        "ix_org_notification_recipients_org_active",
        "org_notification_recipients",
        ["org_id", "active"],
    )

    # 3. crash_packet_deliveries
    op.create_table(
        "crash_packet_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "dispatched",
                "sent",
                "partial",
                "failed",
                "overdue",
                name="crash_packet_delivery_status",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "target_sla_seconds", sa.Integer(), nullable=False, server_default="900"
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=True),
        sa.Column(
            "sent_to",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "failed_to",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "message_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "dispatched_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delivered_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_crash_packet_deliveries_idempotency_key"
        ),
    )
    op.create_index(
        "ix_crash_packet_deliveries_incident_id",
        "crash_packet_deliveries",
        ["incident_id"],
    )
    op.create_index(
        "ix_crash_packet_deliveries_org_id",
        "crash_packet_deliveries",
        ["org_id"],
    )
    op.create_index(
        "ix_crash_packet_deliveries_status_dispatched",
        "crash_packet_deliveries",
        ["status", "dispatched_at_utc"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_crash_packet_deliveries_status_dispatched",
        table_name="crash_packet_deliveries",
    )
    op.drop_index(
        "ix_crash_packet_deliveries_org_id", table_name="crash_packet_deliveries"
    )
    op.drop_index(
        "ix_crash_packet_deliveries_incident_id",
        table_name="crash_packet_deliveries",
    )
    op.drop_table("crash_packet_deliveries")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS crash_packet_delivery_status")

    op.drop_index(
        "ix_org_notification_recipients_org_active",
        table_name="org_notification_recipients",
    )
    op.drop_index(
        "ix_org_notification_recipients_org_id",
        table_name="org_notification_recipients",
    )
    op.drop_table("org_notification_recipients")

    # Note: PostgreSQL does not support removing enum values; the
    # ``accident_occurred`` value remains on downgrade.
