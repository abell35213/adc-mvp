"""normalize user role values to canonical names

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET role = CASE
            WHEN lower(trim(role)) IN ('admin', 'administrator', 'super_admin', 'superadmin') THEN 'admin'
            WHEN lower(trim(role)) IN ('safety_manager', 'safety manager', 'safety-manager', 'manager') THEN 'safety_manager'
            ELSE 'safety_manager'
        END
        """
    )


def downgrade() -> None:
    # Canonical roles are retained on downgrade.
    pass
