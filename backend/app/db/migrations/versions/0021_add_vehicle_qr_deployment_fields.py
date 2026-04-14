"""add vehicle qr deployment lifecycle fields

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-14 00:00:00.000000
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


_vehicle_qr_status = sa.Enum(
    "not_generated",
    "generated",
    "distributed",
    "confirmed",
    name="vehicle_qr_deployment_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    _vehicle_qr_status.create(bind, checkfirst=True)

    op.add_column(
        "org_vehicle_registry",
        sa.Column(
            "qr_deployment_status",
            _vehicle_qr_status,
            nullable=False,
            server_default="not_generated",
        ),
    )
    op.add_column(
        "org_vehicle_registry",
        sa.Column("qr_generated_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "org_vehicle_registry",
        sa.Column("qr_distributed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "org_vehicle_registry",
        sa.Column("qr_confirmed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_org_vehicle_registry_qr_deployment_status",
        "org_vehicle_registry",
        ["qr_deployment_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_vehicle_registry_qr_deployment_status",
        table_name="org_vehicle_registry",
    )
    op.drop_column("org_vehicle_registry", "qr_confirmed_at_utc")
    op.drop_column("org_vehicle_registry", "qr_distributed_at_utc")
    op.drop_column("org_vehicle_registry", "qr_generated_at_utc")
    op.drop_column("org_vehicle_registry", "qr_deployment_status")

    bind = op.get_bind()
    _vehicle_qr_status.drop(bind, checkfirst=True)
