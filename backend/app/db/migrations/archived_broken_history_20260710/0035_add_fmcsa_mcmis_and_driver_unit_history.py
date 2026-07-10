"""add fmcsa mcmis snapshot/inspections + driver_unit_history + carrier identity

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-02 16:00:00.000000

Adds:

* ``orgs.usdot_number`` (carrier identity for the FMCSA MCMIS pull;
  partial unique index on non-null values).
* ``org_vehicle_registry.license_plate`` / ``license_state`` /
  ``dot_unit_type`` (used for FMCSA inspection cross-reference).
* ``driver_unit_history`` (slip-seating: every tractor/trailer a driver
  operated, with a confidence score).
* ``fmcsa_inspection_snapshots`` + ``fmcsa_inspections`` (cached MCMIS
  pull, scoped per-org by USDOT).
* ``incident_driver_violation_history`` (per-incident attribution
  output; low-confidence rows are stored for audit but excluded from
  the brief).
* Extends ``tms_field_map_entity`` enum with ``driver_unit_history``.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


_NEW_TMS_ENTITY_VALUES = ("driver_unit_history",)


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. orgs.usdot_number (single carrier per tenant).
    op.add_column("orgs", sa.Column("usdot_number", sa.Text(), nullable=True))
    op.create_index(
        "ix_orgs_usdot_number_unique",
        "orgs",
        ["usdot_number"],
        unique=True,
        postgresql_where=sa.text("usdot_number IS NOT NULL"),
    )

    # 2. org_vehicle_registry plate/state/dot_unit_type.
    op.add_column(
        "org_vehicle_registry", sa.Column("license_plate", sa.Text(), nullable=True)
    )
    op.add_column(
        "org_vehicle_registry", sa.Column("license_state", sa.Text(), nullable=True)
    )
    op.add_column(
        "org_vehicle_registry",
        sa.Column(
            "dot_unit_type",
            sa.Enum("tractor", "straight_truck", "other", name="dot_unit_type"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_org_vehicle_registry_org_plate_state",
        "org_vehicle_registry",
        ["org_id", "license_plate", "license_state"],
    )

    # 3. driver_unit_history.
    op.create_table(
        "driver_unit_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("adc_driver_id", sa.Text(), nullable=True),
        sa.Column(
            "unit_kind",
            sa.Enum("tractor", "trailer", name="driver_unit_kind"),
            nullable=False,
        ),
        sa.Column("adc_vehicle_id", sa.Text(), nullable=True),
        sa.Column("unit_number", sa.Text(), nullable=True),
        sa.Column("vin", sa.Text(), nullable=True),
        sa.Column("license_plate", sa.Text(), nullable=True),
        sa.Column("license_state", sa.Text(), nullable=True),
        sa.Column("started_at_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "tms",
                "eld",
                "manual",
                "derived_from_assignment",
                name="driver_unit_history_source",
            ),
            nullable=False,
            server_default="tms",
        ),
        sa.Column("source_record_ref", sa.Text(), nullable=True),
        sa.Column(
            "confidence",
            sa.Enum("high", "medium", "low", name="driver_unit_history_confidence"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("confidence_reason", sa.Text(), nullable=True),
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
            ["driver_id"], ["drivers.driver_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_driver_unit_history_org_driver_started",
        "driver_unit_history",
        ["org_id", "driver_id", "started_at_utc"],
    )
    op.create_index(
        "ix_driver_unit_history_org_vin", "driver_unit_history", ["org_id", "vin"]
    )
    op.create_index(
        "ix_driver_unit_history_org_plate_state",
        "driver_unit_history",
        ["org_id", "license_plate", "license_state"],
    )
    op.create_index(
        "ix_driver_unit_history_org_external_id",
        "driver_unit_history",
        ["org_id", "external_id"],
        unique=True,
    )

    # 4. fmcsa_inspection_snapshots.
    op.create_table(
        "fmcsa_inspection_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usdot_number", sa.Text(), nullable=False),
        sa.Column(
            "fetched_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("window_start_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_end_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "record_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "status",
            sa.Enum(
                "succeeded", "partial", "failed", name="fmcsa_snapshot_status"
            ),
            nullable=False,
            server_default="succeeded",
        ),
        sa.Column(
            "error_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_fmcsa_inspection_snapshots_org_fetched",
        "fmcsa_inspection_snapshots",
        ["org_id", "fetched_at_utc"],
    )

    # 5. fmcsa_inspections (normalized rows).
    # NOTE: deliberately omits any driver_* fields that the FMCSA dataset
    # exposes — driver attribution comes only from internal TMS history
    # (see app/services/fmcsa_attribution.py).
    op.create_table(
        "fmcsa_inspections",
        sa.Column("inspection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_number", sa.Text(), nullable=False),
        sa.Column("inspection_date_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("report_state", sa.Text(), nullable=True),
        sa.Column("usdot_number", sa.Text(), nullable=False),
        sa.Column("vehicle_vin", sa.Text(), nullable=True),
        sa.Column("vehicle_license_plate", sa.Text(), nullable=True),
        sa.Column("vehicle_license_state", sa.Text(), nullable=True),
        sa.Column(
            "unit_type",
            sa.Enum("tractor", "trailer", "other", name="fmcsa_unit_type"),
            nullable=False,
            server_default="other",
        ),
        sa.Column("inspection_level", sa.Text(), nullable=True),
        sa.Column(
            "oos_total", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "violation_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "violations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "raw_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["fmcsa_inspection_snapshots.snapshot_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("inspection_id"),
    )
    op.create_index(
        "ix_fmcsa_inspections_org_report_unique",
        "fmcsa_inspections",
        ["org_id", "report_number"],
        unique=True,
    )
    op.create_index(
        "ix_fmcsa_inspections_org_vin",
        "fmcsa_inspections",
        ["org_id", "vehicle_vin"],
    )
    op.create_index(
        "ix_fmcsa_inspections_org_plate_state",
        "fmcsa_inspections",
        ["org_id", "vehicle_license_plate", "vehicle_license_state"],
    )
    op.create_index(
        "ix_fmcsa_inspections_org_date",
        "fmcsa_inspections",
        ["org_id", "inspection_date_utc"],
    )

    # 6. incident_driver_violation_history (per-incident attribution).
    op.create_table(
        "incident_driver_violation_history",
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_history_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "match_basis",
            sa.Enum("vin", "plate_state", name="fmcsa_match_basis"),
            nullable=False,
        ),
        sa.Column(
            "match_confidence",
            sa.Enum(
                "high", "medium", "low", name="fmcsa_match_confidence"
            ),
            nullable=False,
        ),
        sa.Column(
            "included_in_brief",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("excluded_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["fmcsa_inspections.inspection_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"], ["drivers.driver_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["unit_history_id"],
            ["driver_unit_history.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("link_id"),
    )
    op.create_index(
        "ix_incident_driver_violation_history_unique",
        "incident_driver_violation_history",
        ["incident_id", "inspection_id"],
        unique=True,
    )
    op.create_index(
        "ix_incident_driver_violation_history_incident_included",
        "incident_driver_violation_history",
        ["incident_id", "included_in_brief"],
    )

    # 7. Extend tms_field_map_entity enum (Postgres only).
    if is_postgres:
        for value in _NEW_TMS_ENTITY_VALUES:
            op.execute(
                f"ALTER TYPE tms_field_map_entity ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    op.drop_index(
        "ix_incident_driver_violation_history_incident_included",
        table_name="incident_driver_violation_history",
    )
    op.drop_index(
        "ix_incident_driver_violation_history_unique",
        table_name="incident_driver_violation_history",
    )
    op.drop_table("incident_driver_violation_history")

    for index in (
        "ix_fmcsa_inspections_org_date",
        "ix_fmcsa_inspections_org_plate_state",
        "ix_fmcsa_inspections_org_vin",
        "ix_fmcsa_inspections_org_report_unique",
    ):
        op.drop_index(index, table_name="fmcsa_inspections")
    op.drop_table("fmcsa_inspections")

    op.drop_index(
        "ix_fmcsa_inspection_snapshots_org_fetched",
        table_name="fmcsa_inspection_snapshots",
    )
    op.drop_table("fmcsa_inspection_snapshots")

    for index in (
        "ix_driver_unit_history_org_external_id",
        "ix_driver_unit_history_org_plate_state",
        "ix_driver_unit_history_org_vin",
        "ix_driver_unit_history_org_driver_started",
    ):
        op.drop_index(index, table_name="driver_unit_history")
    op.drop_table("driver_unit_history")

    op.drop_index(
        "ix_org_vehicle_registry_org_plate_state",
        table_name="org_vehicle_registry",
    )
    op.drop_column("org_vehicle_registry", "dot_unit_type")
    op.drop_column("org_vehicle_registry", "license_state")
    op.drop_column("org_vehicle_registry", "license_plate")

    op.drop_index("ix_orgs_usdot_number_unique", table_name="orgs")
    op.drop_column("orgs", "usdot_number")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "fmcsa_match_confidence",
            "fmcsa_match_basis",
            "fmcsa_unit_type",
            "fmcsa_snapshot_status",
            "driver_unit_history_confidence",
            "driver_unit_history_source",
            "driver_unit_kind",
            "dot_unit_type",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
