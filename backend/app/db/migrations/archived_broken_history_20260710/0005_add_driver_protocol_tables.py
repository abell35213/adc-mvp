"""add driver protocol tables and org settings

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ──────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE otp_challenge_status AS ENUM ('pending', 'verified', 'expired', 'locked')"
    )
    op.execute(
        "CREATE TYPE driver_assignment_source AS ENUM ('tms', 'eld', 'manual', 'driver_app')"
    )
    op.execute(
        "CREATE TYPE vehicle_qr_token_status AS ENUM ('active', 'revoked', 'rotated')"
    )
    op.execute(
        "CREATE TYPE driver_instruction_scope AS ENUM ('default', 'company', 'insurer')"
    )

    # ── Org settings ────────────────────────────────────────────────
    op.add_column(
        "orgs",
        sa.Column(
            "require_driver_ack",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "orgs",
        sa.Column(
            "sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "orgs",
        sa.Column(
            "voice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("orgs", sa.Column("safety_manager_phone", sa.Text(), nullable=True))

    # ── Driver protocol tables ─────────────────────────────────────
    op.create_table(
        "drivers",
        sa.Column("driver_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("phone_e164", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
    )
    op.create_index("ix_drivers_org_id", "drivers", ["org_id"])
    op.create_index("ix_drivers_phone_e164", "drivers", ["phone_e164"], unique=True)

    op.create_table(
        "otp_challenges",
        sa.Column("challenge_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("phone_e164", sa.Text(), nullable=False),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at_utc", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "verified",
                "expired",
                "locked",
                name="otp_challenge_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("twilio_sid", sa.Text(), nullable=True),
        sa.Column("last_sent_at_utc", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_otp_challenges_phone_e164", "otp_challenges", ["phone_e164"])

    op.create_table(
        "driver_vehicle_assignments",
        sa.Column(
            "assignment_id", UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=False),
        sa.Column(
            "assigned_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("unassigned_at_utc", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "tms",
                "eld",
                "manual",
                "driver_app",
                name="driver_assignment_source",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.driver_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
    )
    op.create_index(
        "ix_driver_vehicle_assignments_org_id",
        "driver_vehicle_assignments",
        ["org_id"],
    )
    op.create_index(
        "ix_driver_vehicle_assignments_driver_id",
        "driver_vehicle_assignments",
        ["driver_id"],
    )
    op.create_index(
        "ix_driver_vehicle_assignments_adc_vehicle_id",
        "driver_vehicle_assignments",
        ["adc_vehicle_id"],
    )

    op.create_table(
        "vehicle_qr_tokens",
        sa.Column("qr_token", sa.Text(), primary_key=True, nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "revoked",
                "rotated",
                name="vehicle_qr_token_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("rotated_from_token", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
    )
    op.create_index("ix_vehicle_qr_tokens_org_id", "vehicle_qr_tokens", ["org_id"])
    op.create_index(
        "ix_vehicle_qr_tokens_adc_vehicle_id", "vehicle_qr_tokens", ["adc_vehicle_id"]
    )
    op.create_index(
        "ix_vehicle_qr_tokens_active_vehicle",
        "vehicle_qr_tokens",
        ["adc_vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "driver_instruction_sets",
        sa.Column(
            "instruction_set_id", UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scope",
            sa.Enum(
                "default",
                "company",
                "insurer",
                name="driver_instruction_scope",
                create_type=False,
            ),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "require_ack", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
    )
    op.create_index(
        "ix_driver_instruction_sets_org_id", "driver_instruction_sets", ["org_id"]
    )

    op.create_table(
        "driver_instruction_steps",
        sa.Column("step_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("instruction_set_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["instruction_set_id"], ["driver_instruction_sets.instruction_set_id"]
        ),
    )
    op.create_index(
        "ix_driver_instruction_steps_set_id",
        "driver_instruction_steps",
        ["instruction_set_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_driver_instruction_steps_set_id", table_name="driver_instruction_steps"
    )
    op.drop_table("driver_instruction_steps")

    op.drop_index(
        "ix_driver_instruction_sets_org_id", table_name="driver_instruction_sets"
    )
    op.drop_table("driver_instruction_sets")

    op.drop_index("ix_vehicle_qr_tokens_active_vehicle", table_name="vehicle_qr_tokens")
    op.drop_index("ix_vehicle_qr_tokens_adc_vehicle_id", table_name="vehicle_qr_tokens")
    op.drop_index("ix_vehicle_qr_tokens_org_id", table_name="vehicle_qr_tokens")
    op.drop_table("vehicle_qr_tokens")

    op.drop_index(
        "ix_driver_vehicle_assignments_adc_vehicle_id",
        table_name="driver_vehicle_assignments",
    )
    op.drop_index(
        "ix_driver_vehicle_assignments_driver_id",
        table_name="driver_vehicle_assignments",
    )
    op.drop_index(
        "ix_driver_vehicle_assignments_org_id",
        table_name="driver_vehicle_assignments",
    )
    op.drop_table("driver_vehicle_assignments")

    op.drop_index("ix_otp_challenges_phone_e164", table_name="otp_challenges")
    op.drop_table("otp_challenges")

    op.drop_index("ix_drivers_phone_e164", table_name="drivers")
    op.drop_index("ix_drivers_org_id", table_name="drivers")
    op.drop_table("drivers")

    op.drop_column("orgs", "safety_manager_phone")
    op.drop_column("orgs", "voice_enabled")
    op.drop_column("orgs", "sms_enabled")
    op.drop_column("orgs", "require_driver_ack")

    op.execute("DROP TYPE driver_instruction_scope")
    op.execute("DROP TYPE vehicle_qr_token_status")
    op.execute("DROP TYPE driver_assignment_source")
    op.execute("DROP TYPE otp_challenge_status")
