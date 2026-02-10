"""add org_id to events, artifacts, exports and adc_driver_id to incidents

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- events.org_id ---
    op.add_column(
        "events",
        sa.Column(
            "org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True
        ),
    )
    op.create_index("ix_events_org_id", "events", ["org_id"])

    # --- artifacts.org_id ---
    op.add_column(
        "artifacts",
        sa.Column(
            "org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True
        ),
    )
    op.create_index("ix_artifacts_org_id", "artifacts", ["org_id"])

    # --- exports.org_id ---
    op.add_column(
        "exports",
        sa.Column(
            "org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=True
        ),
    )
    op.create_index("ix_exports_org_id", "exports", ["org_id"])

    # --- incidents.adc_driver_id (missed in 0001) ---
    op.add_column(
        "incidents",
        sa.Column("adc_driver_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "adc_driver_id")
    op.drop_index("ix_exports_org_id", table_name="exports")
    op.drop_column("exports", "org_id")
    op.drop_index("ix_artifacts_org_id", table_name="artifacts")
    op.drop_column("artifacts", "org_id")
    op.drop_index("ix_events_org_id", table_name="events")
    op.drop_column("events", "org_id")
