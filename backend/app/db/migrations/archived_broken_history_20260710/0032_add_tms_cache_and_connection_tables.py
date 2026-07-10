"""add tms cache and connection tables

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-01 13:00:00.000000

Phase 2 of the ADC demo workflow:

* Adds ``trailers`` (manual + TMS-sourced trailer records).
* Adds ``maintenance_records`` (manual + TMS-sourced maintenance events,
  indexed for the canonical 1-year crash-packet lookup).
* Adds ``tms_connections`` and ``tms_field_maps`` to describe per-org ODBC
  ingest jobs. The ODBC DSN itself is stored only by *secret reference*.
* Adds nullable ``incidents.adc_trailer_id`` so the canonical query can join
  the involved trailer.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1. incidents.adc_trailer_id
    op.add_column("incidents", sa.Column("adc_trailer_id", sa.Text(), nullable=True))

    # 2. trailers
    op.create_table(
        "trailers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adc_trailer_id", sa.Text(), nullable=False),
        sa.Column("vin", sa.Text(), nullable=True),
        sa.Column("make", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("plate", sa.Text(), nullable=True),
        sa.Column(
            "last_inspection_at_utc", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "tms", name="trailer_source"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trailers_org_id", "trailers", ["org_id"])
    op.create_index(
        "ix_trailers_org_adc_trailer_id",
        "trailers",
        ["org_id", "adc_trailer_id"],
        unique=True,
    )
    op.create_index(
        "ix_trailers_org_external_id", "trailers", ["org_id", "external_id"]
    )

    # 3. maintenance_records
    op.create_table(
        "maintenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "asset_kind",
            sa.Enum("tractor", "trailer", name="maintenance_asset_kind"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column(
            "performed_at_utc", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column("vendor", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("mileage", sa.Integer(), nullable=True),
        sa.Column(
            "doc_artifact_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "tms", name="maintenance_source"),
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
            ["doc_artifact_id"], ["artifacts.artifact_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_records_org_id", "maintenance_records", ["org_id"]
    )
    op.create_index(
        "ix_maintenance_records_lookup",
        "maintenance_records",
        ["org_id", "asset_kind", "asset_id", "performed_at_utc"],
    )
    op.create_index(
        "ix_maintenance_records_external_id",
        "maintenance_records",
        ["org_id", "external_id"],
    )

    # 4. tms_connections
    op.create_table(
        "tms_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "vendor_hint",
            sa.Enum(
                "mcleod",
                "tmw",
                "fleetio",
                "whip_around",
                "generic",
                name="tms_vendor_hint",
            ),
            nullable=False,
            server_default="generic",
        ),
        sa.Column("odbc_secret_ref", sa.Text(), nullable=False),
        sa.Column(
            "schedule_cron", sa.Text(), nullable=False, server_default="0 3 * * *"
        ),
        sa.Column(
            "last_synced_at_utc", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "disabled", "error", name="tms_connection_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True
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
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tms_connections_org_id", "tms_connections", ["org_id"])

    # 5. tms_field_maps
    op.create_table(
        "tms_field_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tms_connection_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "entity",
            sa.Enum(
                "trailer", "maintenance_record", name="tms_field_map_entity"
            ),
            nullable=False,
        ),
        sa.Column("source_table", sa.Text(), nullable=False),
        sa.Column("source_column", sa.Text(), nullable=False),
        sa.Column("target_field", sa.Text(), nullable=False),
        sa.Column(
            "transform", sa.Text(), nullable=False, server_default="none"
        ),
        sa.Column(
            "is_key", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tms_connection_id"], ["tms_connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tms_field_maps_tms_connection_id",
        "tms_field_maps",
        ["tms_connection_id"],
    )
    op.create_index(
        "ix_tms_field_maps_conn_entity",
        "tms_field_maps",
        ["tms_connection_id", "entity"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tms_field_maps_conn_entity", table_name="tms_field_maps"
    )
    op.drop_index(
        "ix_tms_field_maps_tms_connection_id", table_name="tms_field_maps"
    )
    op.drop_table("tms_field_maps")

    op.drop_index("ix_tms_connections_org_id", table_name="tms_connections")
    op.drop_table("tms_connections")

    op.drop_index(
        "ix_maintenance_records_external_id", table_name="maintenance_records"
    )
    op.drop_index(
        "ix_maintenance_records_lookup", table_name="maintenance_records"
    )
    op.drop_index(
        "ix_maintenance_records_org_id", table_name="maintenance_records"
    )
    op.drop_table("maintenance_records")

    op.drop_index("ix_trailers_org_external_id", table_name="trailers")
    op.drop_index("ix_trailers_org_adc_trailer_id", table_name="trailers")
    op.drop_index("ix_trailers_org_id", table_name="trailers")
    op.drop_table("trailers")

    op.drop_column("incidents", "adc_trailer_id")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "tms_field_map_entity",
            "tms_connection_status",
            "tms_vendor_hint",
            "maintenance_source",
            "maintenance_asset_kind",
            "trailer_source",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
