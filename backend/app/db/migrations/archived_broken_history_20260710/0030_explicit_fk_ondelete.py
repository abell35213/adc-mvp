"""Add explicit ondelete policies to all foreign keys.

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-24 12:00:00.000000

This migration hardens referential integrity by explicitly setting ON DELETE
policies for every foreign key in the schema. Previously, all FKs used the
database default (NO ACTION on PostgreSQL, which behaves like RESTRICT).

Key policies applied:
- CASCADE: Owned child rows (artifacts→incidents, tokens→sessions, etc.)
- RESTRICT: Tenant roots (org_id in incidents/exports blocks org deletion)
- SET NULL: Soft references where parent may be deleted (assigned_to, created_by)

On SQLite (test env), uses batch_alter_table with recreate="always" to bypass
constraint naming complexity. On PostgreSQL (production), explicitly drops and
recreates each constraint with the correct ON DELETE clause.
"""

from typing import Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


# Table → [(column, referenced_table, ondelete_policy)]
FK_UPDATES = {
    "user_orgs": [
        ("user_id", "users", "CASCADE"),
        ("org_id", "orgs", "CASCADE"),
    ],
    "org_user_invites": [
        ("org_id", "orgs", "CASCADE"),
        ("invited_by_user_id", "users", "SET NULL"),
    ],
    "events": [
        ("org_id", "orgs", "SET NULL"),
        ("incident_id", "incidents", "SET NULL"),
    ],
    "audit_events": [
        ("org_id", "orgs", "RESTRICT"),
        ("incident_id", "incidents", "CASCADE"),
        ("export_id", "exports", "CASCADE"),
        ("artifact_id", "artifacts", "CASCADE"),
    ],
    "incidents": [
        ("org_id", "orgs", "RESTRICT"),
        ("owner_user_id", "users", "SET NULL"),
        ("owner_assigned_by_user_id", "users", "SET NULL"),
    ],
    "case_notes": [
        ("org_id", "orgs", "RESTRICT"),
        ("incident_id", "incidents", "CASCADE"),
        ("created_by_user_id", "users", "SET NULL"),
        ("edited_by_user_id", "users", "SET NULL"),
        ("deleted_by_user_id", "users", "SET NULL"),
    ],
    "case_tasks": [
        ("org_id", "orgs", "RESTRICT"),
        ("incident_id", "incidents", "CASCADE"),
        ("assigned_to_user_id", "users", "SET NULL"),
        ("assigned_by_user_id", "users", "SET NULL"),
        ("completed_by_user_id", "users", "SET NULL"),
        ("canceled_by_user_id", "users", "SET NULL"),
        ("created_by_user_id", "users", "SET NULL"),
    ],
    "case_readiness_overrides": [
        ("org_id", "orgs", "RESTRICT"),
        ("incident_id", "incidents", "CASCADE"),
        ("created_by_user_id", "users", "SET NULL"),
        ("cleared_by_user_id", "users", "SET NULL"),
    ],
    "artifacts": [
        ("org_id", "orgs", "RESTRICT"),
        ("incident_id", "incidents", "CASCADE"),
    ],
    "exports": [
        ("org_id", "orgs", "RESTRICT"),
        ("incident_id", "incidents", "CASCADE"),
        ("requested_by_user_id", "users", "SET NULL"),
        ("retry_parent_export_id", "exports", "SET NULL"),
    ],
    "integration_connections": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "integration_operations": [
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
        ("connection_id", "integration_connections", "SET NULL"),
    ],
    "integration_validation_results": [
        ("org_id", "orgs", "CASCADE"),
        ("connection_id", "integration_connections", "CASCADE"),
    ],
    "integration_operation_status_history": [
        ("operation_id", "integration_operations", "CASCADE"),
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
    ],
    "evidence_requests": [
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
        ("operation_id", "integration_operations", "SET NULL"),
    ],
    "external_mappings": [
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
    ],
    "provider_webhook_events": [
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
    ],
    "message_operations": [
        ("operation_id", "integration_operations", "SET NULL"),
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
    ],
    "message_operation_status_history": [
        ("message_operation_id", "message_operations", "CASCADE"),
    ],
    "sessions": [
        ("user_id", "users", "CASCADE"),
        ("org_id", "orgs", "CASCADE"),
    ],
    "refresh_tokens": [
        ("session_id", "sessions", "CASCADE"),
        ("parent_token_id", "refresh_tokens", "CASCADE"),
    ],
    "org_launch_readiness_snapshots": [
        ("org_id", "orgs", "CASCADE"),
        ("created_by_user_id", "users", "SET NULL"),
    ],
    "org_launch_readiness_step_progress": [
        ("snapshot_id", "org_launch_readiness_snapshots", "CASCADE"),
        ("org_id", "orgs", "CASCADE"),
    ],
    "org_launch_readiness_blockers": [
        ("snapshot_id", "org_launch_readiness_snapshots", "CASCADE"),
        ("org_id", "orgs", "CASCADE"),
    ],
    "org_onboarding_step_completions": [
        ("org_id", "orgs", "CASCADE"),
        ("completed_by_user_id", "users", "SET NULL"),
    ],
    "org_test_incident_runs": [
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
        ("created_by_user_id", "users", "SET NULL"),
    ],
    "org_export_validation_runs": [
        ("org_id", "orgs", "CASCADE"),
        ("incident_id", "incidents", "CASCADE"),
        ("export_id", "exports", "CASCADE"),
        ("created_by_user_id", "users", "SET NULL"),
    ],
    "org_plan_entitlements": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "demo_scenarios": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "help_categories": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "help_articles": [
        ("org_id", "orgs", "CASCADE"),
        ("category_id", "help_categories", "SET NULL"),
        ("created_by_user_id", "users", "SET NULL"),
        ("updated_by_user_id", "users", "SET NULL"),
    ],
    "trust_sections": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "deployment_scope_snapshots": [
        ("org_id", "orgs", "CASCADE"),
        ("captured_by_user_id", "users", "SET NULL"),
    ],
    "help_article_views": [
        ("org_id", "orgs", "CASCADE"),
        ("article_id", "help_articles", "CASCADE"),
        ("viewer_user_id", "users", "SET NULL"),
    ],
    "expansion_readiness_snapshots": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "drivers": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "driver_vehicle_assignments": [
        ("org_id", "orgs", "CASCADE"),
        ("driver_id", "drivers", "CASCADE"),
    ],
    "org_vehicle_registry": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "vehicle_import_jobs": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "driver_import_jobs": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "vehicle_qr_tokens": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "driver_instruction_sets": [
        ("org_id", "orgs", "CASCADE"),
    ],
    "driver_instruction_steps": [
        ("instruction_set_id", "driver_instruction_sets", "CASCADE"),
    ],
}


def upgrade() -> None:
    """Apply explicit ON DELETE policies to all foreign keys."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        # SQLite: use batch mode with recreate="always" to sidestep constraint naming
        for table_name, fks in FK_UPDATES.items():
            with op.batch_alter_table(table_name, recreate="always") as batch_op:
                for col, ref_table, ondelete in fks:
                    # Drop and recreate with ondelete
                    batch_op.drop_constraint(f"{table_name}_{col}_fkey", type_="foreignkey")
                    batch_op.create_foreign_key(
                        f"{table_name}_{col}_fkey",
                        ref_table,
                        [col],
                        [_infer_ref_column(ref_table)],
                        ondelete=ondelete,
                    )
    else:
        # PostgreSQL: use ALTER TABLE with explicit constraint names
        # (SQLAlchemy auto-generates FK names as "{table}_{col}_fkey")
        for table_name, fks in FK_UPDATES.items():
            for col, ref_table, ondelete in fks:
                constraint_name = f"{table_name}_{col}_fkey"
                ref_col = _infer_ref_column(ref_table)
                op.drop_constraint(constraint_name, table_name, type_="foreignkey")
                op.create_foreign_key(
                    constraint_name,
                    table_name,
                    ref_table,
                    [col],
                    [ref_col],
                    ondelete=ondelete,
                )


def downgrade() -> None:
    """Revert to implicit ON DELETE (NO ACTION/RESTRICT on PostgreSQL)."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        for table_name, fks in FK_UPDATES.items():
            with op.batch_alter_table(table_name, recreate="always") as batch_op:
                for col, ref_table, _ in fks:
                    batch_op.drop_constraint(f"{table_name}_{col}_fkey", type_="foreignkey")
                    batch_op.create_foreign_key(
                        f"{table_name}_{col}_fkey",
                        ref_table,
                        [col],
                        [_infer_ref_column(ref_table)],
                        # Omit ondelete to revert to default
                    )
    else:
        for table_name, fks in FK_UPDATES.items():
            for col, ref_table, _ in fks:
                constraint_name = f"{table_name}_{col}_fkey"
                ref_col = _infer_ref_column(ref_table)
                op.drop_constraint(constraint_name, table_name, type_="foreignkey")
                op.create_foreign_key(
                    constraint_name,
                    table_name,
                    ref_table,
                    [col],
                    [ref_col],
                )


def _infer_ref_column(ref_table: str) -> str:
    """Infer the primary key column name for the referenced table."""
    # Special cases
    if ref_table == "orgs":
        return "id"
    if ref_table == "users":
        return "id"
    if ref_table == "incidents":
        return "incident_id"
    if ref_table == "artifacts":
        return "artifact_id"
    if ref_table == "exports":
        return "export_id"
    if ref_table == "sessions":
        return "session_id"
    if ref_table == "refresh_tokens":
        return "token_id"
    if ref_table == "drivers":
        return "driver_id"
    if ref_table == "integration_connections":
        return "connection_id"
    if ref_table == "integration_operations":
        return "operation_id"
    if ref_table == "message_operations":
        return "message_operation_id"
    if ref_table == "help_categories":
        return "category_id"
    if ref_table == "help_articles":
        return "article_id"
    if ref_table == "org_launch_readiness_snapshots":
        return "snapshot_id"
    if ref_table == "driver_instruction_sets":
        return "instruction_set_id"
    # Default pattern
    return f"{ref_table.rstrip('s')}_id"
