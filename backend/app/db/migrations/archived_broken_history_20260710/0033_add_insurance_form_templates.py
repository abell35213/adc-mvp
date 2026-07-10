"""add insurance form templates, fields, and fillings

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-01 19:30:00.000000

Phase 3 of the ADC demo workflow: operator-uploaded blank insurance form
templates, the per-field map (with dot-notation source paths into the
canonical CrashPacketRow), and a per-incident fill log.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1. insurance_form_templates
    op.create_table(
        "insurance_form_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("carrier", sa.Text(), nullable=True),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "finalized",
                "archived",
                name="insurance_form_template_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("s3_bucket", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
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
        sa.Column(
            "finalized_at_utc", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_insurance_form_templates_org_id",
        "insurance_form_templates",
        ["org_id"],
    )
    op.create_index(
        "ix_insurance_form_templates_org_name_version",
        "insurance_form_templates",
        ["org_id", "name", "version"],
        unique=True,
    )

    # 2. insurance_form_template_fields
    op.create_table(
        "insurance_form_template_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "template_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "text",
                "date",
                "checkbox",
                "signature",
                name="insurance_form_field_kind",
            ),
            nullable=False,
            server_default="text",
        ),
        sa.Column("bbox_json", postgresql.JSONB(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column(
            "transform", sa.Text(), nullable=False, server_default="none"
        ),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["insurance_form_templates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_insurance_form_template_fields_template_id",
        "insurance_form_template_fields",
        ["template_id"],
    )
    op.create_index(
        "ix_insurance_form_template_fields_template_name",
        "insurance_form_template_fields",
        ["template_id", "name"],
        unique=True,
    )

    # 3. insurance_form_fillings
    op.create_table(
        "insurance_form_fillings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "incident_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "template_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "filled",
                "failed",
                name="insurance_form_filling_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "payload_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("payload_hash", sa.Text(), nullable=True),
        sa.Column(
            "output_artifact_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "missing_required_fields",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "filled_at_utc", sa.TIMESTAMP(timezone=True), nullable=True
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
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["insurance_form_templates.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["output_artifact_id"],
            ["artifacts.artifact_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_insurance_form_fillings_incident_id",
        "insurance_form_fillings",
        ["incident_id"],
    )
    op.create_index(
        "ix_insurance_form_fillings_template_id",
        "insurance_form_fillings",
        ["template_id"],
    )
    op.create_index(
        "ix_insurance_form_fillings_payload_hash",
        "insurance_form_fillings",
        ["payload_hash"],
    )
    op.create_index(
        "ix_insurance_form_fillings_incident_template_hash",
        "insurance_form_fillings",
        ["incident_id", "template_id", "payload_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_insurance_form_fillings_incident_template_hash",
        table_name="insurance_form_fillings",
    )
    op.drop_index(
        "ix_insurance_form_fillings_payload_hash",
        table_name="insurance_form_fillings",
    )
    op.drop_index(
        "ix_insurance_form_fillings_template_id",
        table_name="insurance_form_fillings",
    )
    op.drop_index(
        "ix_insurance_form_fillings_incident_id",
        table_name="insurance_form_fillings",
    )
    op.drop_table("insurance_form_fillings")

    op.drop_index(
        "ix_insurance_form_template_fields_template_name",
        table_name="insurance_form_template_fields",
    )
    op.drop_index(
        "ix_insurance_form_template_fields_template_id",
        table_name="insurance_form_template_fields",
    )
    op.drop_table("insurance_form_template_fields")

    op.drop_index(
        "ix_insurance_form_templates_org_name_version",
        table_name="insurance_form_templates",
    )
    op.drop_index(
        "ix_insurance_form_templates_org_id",
        table_name="insurance_form_templates",
    )
    op.drop_table("insurance_form_templates")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "insurance_form_filling_status",
            "insurance_form_field_kind",
            "insurance_form_template_status",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
