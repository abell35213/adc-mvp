"""add model improvements: foreign keys, enums, timestamps, and indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute(
        "CREATE TYPE incident_status AS ENUM ('open', 'evidence_capturing', 'closed')"
    )
    op.execute(
        "CREATE TYPE artifact_status AS ENUM ('pending', 'captured', 'unavailable')"
    )
    op.execute(
        "CREATE TYPE export_status AS ENUM ('requested', 'processing', 'ready', 'failed')"
    )

    # --- Update Incident.status column to use enum ---
    # Store existing status values temporarily
    op.execute(
        "ALTER TABLE incidents ALTER COLUMN status TYPE incident_status USING status::incident_status"
    )

    # --- Update Artifact.status column to use enum ---
    op.execute(
        "ALTER TABLE artifacts ALTER COLUMN status TYPE artifact_status USING status::artifact_status"
    )

    # --- Update Export.status column to use enum ---
    op.execute(
        "ALTER TABLE exports ALTER COLUMN status TYPE export_status USING status::export_status"
    )

    # --- Add foreign key constraints ---
    # Event.incident_id -> Incident.incident_id
    op.create_foreign_key(
        "fk_events_incident_id", "events", "incidents", ["incident_id"], ["incident_id"]
    )

    # Artifact.incident_id -> Incident.incident_id
    op.create_foreign_key(
        "fk_artifacts_incident_id",
        "artifacts",
        "incidents",
        ["incident_id"],
        ["incident_id"],
    )

    # Export.incident_id -> Incident.incident_id
    op.create_foreign_key(
        "fk_exports_incident_id",
        "exports",
        "incidents",
        ["incident_id"],
        ["incident_id"],
    )

    # --- Add created_at_utc to Event and Artifact ---
    op.add_column(
        "events",
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "artifacts",
        sa.Column(
            "created_at_utc",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Add composite indexes ---
    # Event indexes
    op.create_index("ix_events_org_incident", "events", ["org_id", "incident_id"])
    op.create_index(
        "ix_events_org_type_occurred",
        "events",
        ["org_id", "event_type", "occurred_at_utc"],
    )

    # Artifact indexes
    op.create_index("ix_artifacts_org_incident", "artifacts", ["org_id", "incident_id"])
    op.create_index(
        "ix_artifacts_incident_type", "artifacts", ["incident_id", "artifact_type"]
    )

    # Export indexes
    op.create_index("ix_exports_org_incident", "exports", ["org_id", "incident_id"])


def downgrade() -> None:
    # --- Drop composite indexes ---
    op.drop_index("ix_exports_org_incident", table_name="exports")
    op.drop_index("ix_artifacts_incident_type", table_name="artifacts")
    op.drop_index("ix_artifacts_org_incident", table_name="artifacts")
    op.drop_index("ix_events_org_type_occurred", table_name="events")
    op.drop_index("ix_events_org_incident", table_name="events")

    # --- Drop created_at_utc columns ---
    op.drop_column("artifacts", "created_at_utc")
    op.drop_column("events", "created_at_utc")

    # --- Drop foreign key constraints ---
    op.drop_constraint("fk_exports_incident_id", "exports", type_="foreignkey")
    op.drop_constraint("fk_artifacts_incident_id", "artifacts", type_="foreignkey")
    op.drop_constraint("fk_events_incident_id", "events", type_="foreignkey")

    # --- Revert status columns to Text type ---
    op.execute("ALTER TABLE exports ALTER COLUMN status TYPE text USING status::text")
    op.execute("ALTER TABLE artifacts ALTER COLUMN status TYPE text USING status::text")
    op.execute("ALTER TABLE incidents ALTER COLUMN status TYPE text USING status::text")

    # --- Drop enum types ---
    op.execute("DROP TYPE export_status")
    op.execute("DROP TYPE artifact_status")
    op.execute("DROP TYPE incident_status")
