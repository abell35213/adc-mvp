"""add immutable audit_events table

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("export_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("retention_expires_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("retention_purged_at_utc", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at_utc",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.artifact_id"]),
        sa.ForeignKeyConstraint(["export_id"], ["exports.export_id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_audit_events_org_id", "audit_events", ["org_id"], unique=False)
    op.create_index("ix_audit_events_incident_id", "audit_events", ["incident_id"], unique=False)
    op.create_index("ix_audit_events_export_id", "audit_events", ["export_id"], unique=False)
    op.create_index("ix_audit_events_artifact_id", "audit_events", ["artifact_id"], unique=False)
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_occurred_at_utc", "audit_events", ["occurred_at_utc"], unique=False)

    op.create_index(
        "ix_audit_events_org_occurred",
        "audit_events",
        ["org_id", "occurred_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_org_incident_occurred",
        "audit_events",
        ["org_id", "incident_id", "occurred_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_org_export_occurred",
        "audit_events",
        ["org_id", "export_id", "occurred_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_org_actor_occurred",
        "audit_events",
        ["org_id", "actor_id", "occurred_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_org_event_type_occurred",
        "audit_events",
        ["org_id", "event_type", "occurred_at_utc"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_events_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'audit_events rows are append-only and cannot be deleted';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF NEW.org_id IS DISTINCT FROM OLD.org_id
                    OR NEW.incident_id IS DISTINCT FROM OLD.incident_id
                    OR NEW.export_id IS DISTINCT FROM OLD.export_id
                    OR NEW.artifact_id IS DISTINCT FROM OLD.artifact_id
                    OR NEW.actor_type IS DISTINCT FROM OLD.actor_type
                    OR NEW.actor_id IS DISTINCT FROM OLD.actor_id
                    OR NEW.action IS DISTINCT FROM OLD.action
                    OR NEW.event_type IS DISTINCT FROM OLD.event_type
                    OR NEW.outcome IS DISTINCT FROM OLD.outcome
                    OR NEW.metadata_json IS DISTINCT FROM OLD.metadata_json
                    OR NEW.occurred_at_utc IS DISTINCT FROM OLD.occurred_at_utc
                    OR NEW.created_at_utc IS DISTINCT FROM OLD.created_at_utc
                THEN
                    RAISE EXCEPTION 'audit_events rows are append-only; only retention fields are mutable';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_prevent_audit_events_mutation
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_events_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_events_mutation ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_events_mutation")

    op.drop_index("ix_audit_events_org_event_type_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_org_actor_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_org_export_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_org_incident_occurred", table_name="audit_events")
    op.drop_index("ix_audit_events_org_occurred", table_name="audit_events")

    op.drop_index("ix_audit_events_occurred_at_utc", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_index("ix_audit_events_artifact_id", table_name="audit_events")
    op.drop_index("ix_audit_events_export_id", table_name="audit_events")
    op.drop_index("ix_audit_events_incident_id", table_name="audit_events")
    op.drop_index("ix_audit_events_org_id", table_name="audit_events")

    op.drop_table("audit_events")
