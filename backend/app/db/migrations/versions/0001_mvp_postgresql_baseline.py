"""mvp postgresql baseline

Revision ID: 0001
Revises: 
Create Date: 2026-07-10

This pre-production baseline replaces the incomplete historical migration chain.
The archived chain is retained under app/db/migrations/archived_broken_history_20260710
for audit/reference, outside Alembic's active versions directory.
"""

from typing import Sequence, Union

from alembic import op

from app.db.models import Base


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)
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
        DROP TRIGGER IF EXISTS trg_prevent_audit_events_mutation ON audit_events;
        CREATE TRIGGER trg_prevent_audit_events_mutation
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_events_mutation();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_events_mutation ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_events_mutation")
    Base.metadata.drop_all(bind=bind, checkfirst=True)
