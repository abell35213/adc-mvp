"""add dispatch instructions, weigh tickets, loading dock reports

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-02 00:00:00.000000

Phase 3 of the crash-packet workflow:

* Adds ``dispatch_instructions`` (paper or TMS-recorded trip dispatch).
* Adds ``weigh_station_reports`` (carrier-recorded weigh ticket; future
  external feeds — FMCSA SAFER, PrePass — will plug into this same table).
* Adds ``loading_dock_reports`` (cargo + securement, with photos linked
  many-to-one via a new ``artifacts.loading_dock_report_id`` FK).
* Adds ``loading_dock_report_id`` to ``artifacts`` so dock photos (and the
  follow-on imaging-integration project's digitized weigh tickets and
  dispatch sheets) can attach to a report without further schema churn.
* Extends ``tms_field_map_entity`` enum with three new values so existing
  TMS sync wiring can map vendor columns into the new tables.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


_NEW_TMS_ENTITY_VALUES = (
    "dispatch_instruction",
    "weigh_station_report",
    "loading_dock_report",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. dispatch_instructions
    op.create_table(
        "dispatch_instructions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adc_driver_id", sa.Text(), nullable=True),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=True),
        sa.Column("adc_trailer_id", sa.Text(), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dispatch_id", sa.Text(), nullable=True),
        sa.Column("load_number", sa.Text(), nullable=True),
        sa.Column("dispatched_by", sa.Text(), nullable=True),
        sa.Column("dispatched_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "pickup_appointment_at_utc", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "delivery_appointment_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("eta_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("origin_address", sa.Text(), nullable=True),
        sa.Column("destination_address", sa.Text(), nullable=True),
        sa.Column("hos_remaining_drive_minutes", sa.Integer(), nullable=True),
        sa.Column("hos_remaining_duty_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "forced_dispatch_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.Enum("manual", "tms", name="dispatch_instruction_source"),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("synced_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dispatch_instructions_org_id", "dispatch_instructions", ["org_id"]
    )
    op.create_index(
        "ix_dispatch_instructions_org_driver_dispatched",
        "dispatch_instructions",
        ["org_id", "adc_driver_id", "dispatched_at_utc"],
    )
    op.create_index(
        "ix_dispatch_instructions_org_external_id",
        "dispatch_instructions",
        ["org_id", "external_id"],
        unique=True,
    )
    op.create_index(
        "ix_dispatch_instructions_org_incident",
        "dispatch_instructions",
        ["org_id", "incident_id"],
    )

    # 2. weigh_station_reports
    op.create_table(
        "weigh_station_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=True),
        sa.Column("adc_trailer_id", sa.Text(), nullable=True),
        sa.Column(
            "dispatch_instruction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("weighed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("station_name", sa.Text(), nullable=True),
        sa.Column("station_location", sa.Text(), nullable=True),
        sa.Column("ticket_number", sa.Text(), nullable=True),
        sa.Column("gross_weight_lb", sa.Integer(), nullable=True),
        sa.Column("steer_axle_weight_lb", sa.Integer(), nullable=True),
        sa.Column("drive_axle_weight_lb", sa.Integer(), nullable=True),
        sa.Column("trailer_axle_weight_lb", sa.Integer(), nullable=True),
        sa.Column("legal_limit_lb", sa.Integer(), nullable=True),
        sa.Column(
            "is_over_legal_limit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "result",
            sa.Enum(
                "pass",
                "bypass",
                "cited",
                "out_of_service",
                name="weigh_station_result",
            ),
            nullable=True,
        ),
        sa.Column("citation_text", sa.Text(), nullable=True),
        sa.Column("inspector_name", sa.Text(), nullable=True),
        sa.Column("doc_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "source",
            sa.Enum("manual", "tms", name="weigh_station_report_source"),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("synced_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dispatch_instruction_id"],
            ["dispatch_instructions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["doc_artifact_id"], ["artifacts.artifact_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_weigh_station_reports_org_id", "weigh_station_reports", ["org_id"]
    )
    op.create_index(
        "ix_weigh_station_reports_org_vehicle_weighed",
        "weigh_station_reports",
        ["org_id", "adc_vehicle_id", "weighed_at_utc"],
    )
    op.create_index(
        "ix_weigh_station_reports_org_external_id",
        "weigh_station_reports",
        ["org_id", "external_id"],
        unique=True,
    )
    op.create_index(
        "ix_weigh_station_reports_org_incident",
        "weigh_station_reports",
        ["org_id", "incident_id"],
    )

    # 3. loading_dock_reports
    op.create_table(
        "loading_dock_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adc_trailer_id", sa.Text(), nullable=True),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=True),
        sa.Column(
            "dispatch_instruction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loaded_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("facility_name", sa.Text(), nullable=True),
        sa.Column("facility_address", sa.Text(), nullable=True),
        sa.Column("commodity", sa.Text(), nullable=True),
        sa.Column("pieces", sa.Integer(), nullable=True),
        sa.Column("gross_weight_lb", sa.Integer(), nullable=True),
        sa.Column("net_weight_lb", sa.Integer(), nullable=True),
        sa.Column("seal_number", sa.Text(), nullable=True),
        sa.Column("securement_method", sa.Text(), nullable=True),
        sa.Column("weight_distribution_notes", sa.Text(), nullable=True),
        sa.Column(
            "is_overloaded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_improperly_loaded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("loaded_by", sa.Text(), nullable=True),
        sa.Column("dock_supervisor", sa.Text(), nullable=True),
        sa.Column(
            "signature_artifact_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "tms", name="loading_dock_report_source"),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("synced_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dispatch_instruction_id"],
            ["dispatch_instructions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["signature_artifact_id"],
            ["artifacts.artifact_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_loading_dock_reports_org_id", "loading_dock_reports", ["org_id"]
    )
    op.create_index(
        "ix_loading_dock_reports_org_trailer_loaded",
        "loading_dock_reports",
        ["org_id", "adc_trailer_id", "loaded_at_utc"],
    )
    op.create_index(
        "ix_loading_dock_reports_org_external_id",
        "loading_dock_reports",
        ["org_id", "external_id"],
        unique=True,
    )
    op.create_index(
        "ix_loading_dock_reports_org_incident",
        "loading_dock_reports",
        ["org_id", "incident_id"],
    )

    # 4. artifacts.loading_dock_report_id (many-to-one for dock photos +
    #    future imaging-integration digitized weigh tickets / dispatch sheets).
    op.add_column(
        "artifacts",
        sa.Column(
            "loading_dock_report_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_artifacts_loading_dock_report_id",
        "artifacts",
        "loading_dock_reports",
        ["loading_dock_report_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_artifacts_loading_dock_report_id",
        "artifacts",
        ["loading_dock_report_id"],
    )

    # 5. Extend tms_field_map_entity enum (Postgres only — SQLite enums are
    #    just CHECK constraints recreated from the model on each connect).
    if is_postgres:
        for value in _NEW_TMS_ENTITY_VALUES:
            op.execute(
                f"ALTER TYPE tms_field_map_entity ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    op.drop_index(
        "ix_artifacts_loading_dock_report_id", table_name="artifacts"
    )
    op.drop_constraint(
        "fk_artifacts_loading_dock_report_id", "artifacts", type_="foreignkey"
    )
    op.drop_column("artifacts", "loading_dock_report_id")

    for table in (
        "loading_dock_reports",
        "weigh_station_reports",
        "dispatch_instructions",
    ):
        for index in (
            f"ix_{table}_org_incident",
            f"ix_{table}_org_external_id",
            f"ix_{table}_org_id",
        ):
            op.drop_index(index, table_name=table)
    op.drop_index(
        "ix_loading_dock_reports_org_trailer_loaded",
        table_name="loading_dock_reports",
    )
    op.drop_index(
        "ix_weigh_station_reports_org_vehicle_weighed",
        table_name="weigh_station_reports",
    )
    op.drop_index(
        "ix_dispatch_instructions_org_driver_dispatched",
        table_name="dispatch_instructions",
    )

    op.drop_table("loading_dock_reports")
    op.drop_table("weigh_station_reports")
    op.drop_table("dispatch_instructions")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Drop the per-table source enums. The ``tms_field_map_entity`` enum
        # cannot be reverted in place (Postgres does not support removing enum
        # values); leaving the new values in the type is harmless because
        # ``tms_field_maps`` rows pointing at the dropped tables would have
        # already been removed via the FK CASCADE on TmsConnection deletion
        # by the time anyone is downgrading past this revision.
        for enum_name in (
            "loading_dock_report_source",
            "weigh_station_report_source",
            "dispatch_instruction_source",
            "weigh_station_result",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
