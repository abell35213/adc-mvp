"""extend export schema with typed metadata and progress tracking

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE export_type AS ENUM ('court_defense', 'insurer_packet', 'internal_review', 'compliance_audit')"
    )
    op.execute(
        "CREATE TYPE export_progress_stage AS ENUM ('request_accepted', 'gathering_incident_data', 'assembling_documents', 'packaging_evidence', 'uploading_export', 'ready_for_download')"
    )

    op.execute("ALTER TYPE export_status ADD VALUE IF NOT EXISTS 'queued'")
    op.execute("ALTER TYPE export_status ADD VALUE IF NOT EXISTS 'expired'")

    op.add_column(
        "exports",
        sa.Column(
            "export_type",
            sa.Enum(name="export_type", create_type=False),
            nullable=False,
            server_default="court_defense",
        ),
    )
    op.add_column(
        "exports",
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "exports",
        sa.Column(
            "options_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "exports",
        sa.Column(
            "progress_stage",
            sa.Enum(name="export_progress_stage", create_type=False),
            nullable=False,
            server_default="request_accepted",
        ),
    )
    op.add_column("exports", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("exports", sa.Column("package_sha256", sa.Text(), nullable=True))
    op.add_column("exports", sa.Column("byte_size", sa.BigInteger(), nullable=True))
    op.add_column(
        "exports",
        sa.Column("artifact_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "exports",
        sa.Column(
            "timeline_event_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "exports",
        sa.Column(
            "requested_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "exports",
        sa.Column("processing_started_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "exports",
        sa.Column("completed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "exports",
        sa.Column("expires_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "exports",
        sa.Column(
            "updated_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.execute("UPDATE exports SET requested_at_utc = created_at_utc WHERE requested_at_utc IS NULL")
    op.execute("UPDATE exports SET updated_at_utc = created_at_utc WHERE updated_at_utc IS NULL")


def downgrade() -> None:
    op.drop_column("exports", "updated_at_utc")
    op.drop_column("exports", "expires_at_utc")
    op.drop_column("exports", "completed_at_utc")
    op.drop_column("exports", "processing_started_at_utc")
    op.drop_column("exports", "requested_at_utc")
    op.drop_column("exports", "timeline_event_count")
    op.drop_column("exports", "artifact_count")
    op.drop_column("exports", "byte_size")
    op.drop_column("exports", "package_sha256")
    op.drop_column("exports", "error_message")
    op.drop_column("exports", "progress_stage")
    op.drop_column("exports", "options_json")
    op.drop_column("exports", "requested_by_user_id")
    op.drop_column("exports", "export_type")

    op.execute("DROP TYPE export_progress_stage")
    op.execute("DROP TYPE export_type")
