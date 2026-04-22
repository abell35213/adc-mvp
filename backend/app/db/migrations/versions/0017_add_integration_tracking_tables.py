"""Add integration tracking and webhook persistence tables.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


integration_connection_status = sa.Enum(
    "pending", "active", "inactive", "error", name="integration_connection_status"
)
integration_operation_status = sa.Enum(
    "queued", "running", "succeeded", "failed", "canceled", name="integration_operation_status"
)
evidence_request_status = sa.Enum(
    "open", "in_progress", "fulfilled", "failed", "canceled", name="evidence_request_status"
)
provider_webhook_event_status = sa.Enum(
    "received", "processed", "ignored", "failed", name="provider_webhook_event_status"
)
message_operation_status = sa.Enum(
    "queued", "sent", "delivered", "failed", "received", name="message_operation_status"
)


def upgrade() -> None:
    bind = op.get_bind()
    integration_connection_status.create(bind, checkfirst=True)
    integration_operation_status.create(bind, checkfirst=True)
    evidence_request_status.create(bind, checkfirst=True)
    provider_webhook_event_status.create(bind, checkfirst=True)
    message_operation_status.create(bind, checkfirst=True)

    op.create_table(
        "integration_connections",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("status", integration_connection_status, nullable=False, server_default="pending"),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("credentials_ref", sa.Text(), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_synced_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("connection_id"),
    )
    op.create_index("ix_integration_connections_org_id", "integration_connections", ["org_id"])
    op.create_index("ix_integration_connections_provider", "integration_connections", ["provider"])
    op.create_index("ix_integration_connections_domain", "integration_connections", ["domain"])
    op.create_index("ix_integration_connections_status", "integration_connections", ["status"])
    op.create_index("ix_integration_connections_external_reference", "integration_connections", ["external_reference"])
    op.create_index(
        "ix_integration_connections_org_provider_domain_status",
        "integration_connections",
        ["org_id", "provider", "domain", "status"],
    )
    op.create_index(
        "ix_integration_connections_org_provider_updated",
        "integration_connections",
        ["org_id", "provider", "updated_at_utc"],
    )

    op.create_table(
        "integration_operations",
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("status", integration_operation_status, nullable=False, server_default="queued"),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["connection_id"], ["integration_connections.connection_id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("operation_id"),
    )
    for index_column in [
        "org_id",
        "incident_id",
        "connection_id",
        "provider",
        "domain",
        "operation_type",
        "status",
        "correlation_id",
        "external_reference",
    ]:
        op.create_index(f"ix_integration_operations_{index_column}", "integration_operations", [index_column])
    op.create_index(
        "ix_integration_operations_org_provider_domain_status_requested",
        "integration_operations",
        ["org_id", "provider", "domain", "status", "requested_at_utc"],
    )
    op.create_index(
        "ix_integration_operations_org_incident_status",
        "integration_operations",
        ["org_id", "incident_id", "status"],
    )

    op.create_table(
        "integration_operation_status_history",
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["integration_operations.operation_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("history_id"),
    )
    for index_column in [
        "operation_id",
        "org_id",
        "incident_id",
        "provider",
        "domain",
        "to_status",
        "correlation_id",
        "external_reference",
    ]:
        op.create_index(
            f"ix_integration_operation_status_history_{index_column}",
            "integration_operation_status_history",
            [index_column],
        )
    op.create_index(
        "ix_integration_op_history_org_provider_domain_to_status_created",
        "integration_operation_status_history",
        ["org_id", "provider", "domain", "to_status", "created_at_utc"],
    )
    op.create_index(
        "ix_integration_op_history_org_incident_created",
        "integration_operation_status_history",
        ["org_id", "incident_id", "created_at_utc"],
    )

    op.create_table(
        "evidence_requests",
        sa.Column("evidence_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("status", evidence_request_status, nullable=False, server_default="open"),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("request_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("response_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("requested_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("due_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("fulfilled_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["integration_operations.operation_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("evidence_request_id"),
    )
    for index_column in [
        "org_id",
        "incident_id",
        "operation_id",
        "provider",
        "domain",
        "status",
        "correlation_id",
        "external_reference",
    ]:
        op.create_index(f"ix_evidence_requests_{index_column}", "evidence_requests", [index_column])
    op.create_index(
        "ix_evidence_requests_org_provider_domain_status_requested",
        "evidence_requests",
        ["org_id", "provider", "domain", "status", "requested_at_utc"],
    )
    op.create_index(
        "ix_evidence_requests_org_incident_status",
        "evidence_requests",
        ["org_id", "incident_id", "status"],
    )

    op.create_table(
        "external_mappings",
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("internal_entity_type", sa.Text(), nullable=False),
        sa.Column("internal_entity_id", sa.Text(), nullable=False),
        sa.Column("external_reference", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("mapping_id"),
    )
    for index_column in [
        "org_id",
        "incident_id",
        "provider",
        "domain",
        "internal_entity_type",
        "internal_entity_id",
        "external_reference",
    ]:
        op.create_index(f"ix_external_mappings_{index_column}", "external_mappings", [index_column])
    op.create_index(
        "ix_external_mappings_org_provider_domain_entity",
        "external_mappings",
        ["org_id", "provider", "domain", "internal_entity_type", "internal_entity_id"],
    )
    op.create_index(
        "ix_external_mappings_org_provider_external_ref",
        "external_mappings",
        ["org_id", "provider", "external_reference"],
    )
    op.create_index("ix_external_mappings_org_incident", "external_mappings", ["org_id", "incident_id"])

    op.create_table(
        "provider_webhook_events",
        sa.Column("webhook_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", provider_webhook_event_status, nullable=False, server_default="received"),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("webhook_event_id"),
    )
    for index_column in [
        "org_id",
        "incident_id",
        "provider",
        "domain",
        "event_type",
        "status",
        "correlation_id",
        "external_reference",
    ]:
        op.create_index(
            f"ix_provider_webhook_events_{index_column}",
            "provider_webhook_events",
            [index_column],
        )
    op.create_index(
        "ix_provider_webhook_events_org_provider_domain_status_received",
        "provider_webhook_events",
        ["org_id", "provider", "domain", "status", "received_at_utc"],
    )
    op.create_index(
        "ix_provider_webhook_events_org_incident_received",
        "provider_webhook_events",
        ["org_id", "incident_id", "received_at_utc"],
    )

    op.create_table(
        "message_operations",
        sa.Column("message_operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("status", message_operation_status, nullable=False, server_default="queued"),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("template_name", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sent_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivered_at_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at_utc", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.incident_id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["integration_operations.operation_id"]),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("message_operation_id"),
    )
    for index_column in [
        "operation_id",
        "org_id",
        "incident_id",
        "provider",
        "domain",
        "channel",
        "direction",
        "status",
        "correlation_id",
        "external_reference",
    ]:
        op.create_index(f"ix_message_operations_{index_column}", "message_operations", [index_column])
    op.create_index(
        "ix_message_operations_org_provider_domain_status_created",
        "message_operations",
        ["org_id", "provider", "domain", "status", "created_at_utc"],
    )
    op.create_index(
        "ix_message_operations_org_incident_created",
        "message_operations",
        ["org_id", "incident_id", "created_at_utc"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_message_operations_org_incident_created", table_name="message_operations")
    op.drop_index("ix_message_operations_org_provider_domain_status_created", table_name="message_operations")
    for index_column in [
        "external_reference",
        "correlation_id",
        "status",
        "direction",
        "channel",
        "domain",
        "provider",
        "incident_id",
        "org_id",
        "operation_id",
    ]:
        op.drop_index(f"ix_message_operations_{index_column}", table_name="message_operations")
    op.drop_table("message_operations")

    op.drop_index("ix_provider_webhook_events_org_incident_received", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_org_provider_domain_status_received", table_name="provider_webhook_events")
    for index_column in [
        "external_reference",
        "correlation_id",
        "status",
        "event_type",
        "domain",
        "provider",
        "incident_id",
        "org_id",
    ]:
        op.drop_index(f"ix_provider_webhook_events_{index_column}", table_name="provider_webhook_events")
    op.drop_table("provider_webhook_events")

    op.drop_index("ix_external_mappings_org_incident", table_name="external_mappings")
    op.drop_index("ix_external_mappings_org_provider_external_ref", table_name="external_mappings")
    op.drop_index("ix_external_mappings_org_provider_domain_entity", table_name="external_mappings")
    for index_column in [
        "external_reference",
        "internal_entity_id",
        "internal_entity_type",
        "domain",
        "provider",
        "incident_id",
        "org_id",
    ]:
        op.drop_index(f"ix_external_mappings_{index_column}", table_name="external_mappings")
    op.drop_table("external_mappings")

    op.drop_index("ix_evidence_requests_org_incident_status", table_name="evidence_requests")
    op.drop_index("ix_evidence_requests_org_provider_domain_status_requested", table_name="evidence_requests")
    for index_column in [
        "external_reference",
        "correlation_id",
        "status",
        "domain",
        "provider",
        "operation_id",
        "incident_id",
        "org_id",
    ]:
        op.drop_index(f"ix_evidence_requests_{index_column}", table_name="evidence_requests")
    op.drop_table("evidence_requests")

    op.drop_index("ix_integration_op_history_org_incident_created", table_name="integration_operation_status_history")
    op.drop_index(
        "ix_integration_op_history_org_provider_domain_to_status_created",
        table_name="integration_operation_status_history",
    )
    for index_column in [
        "external_reference",
        "correlation_id",
        "to_status",
        "domain",
        "provider",
        "incident_id",
        "org_id",
        "operation_id",
    ]:
        op.drop_index(
            f"ix_integration_operation_status_history_{index_column}",
            table_name="integration_operation_status_history",
        )
    op.drop_table("integration_operation_status_history")

    op.drop_index("ix_integration_operations_org_incident_status", table_name="integration_operations")
    op.drop_index(
        "ix_integration_operations_org_provider_domain_status_requested",
        table_name="integration_operations",
    )
    for index_column in [
        "external_reference",
        "correlation_id",
        "status",
        "operation_type",
        "domain",
        "provider",
        "connection_id",
        "incident_id",
        "org_id",
    ]:
        op.drop_index(f"ix_integration_operations_{index_column}", table_name="integration_operations")
    op.drop_table("integration_operations")

    op.drop_index("ix_integration_connections_org_provider_updated", table_name="integration_connections")
    op.drop_index(
        "ix_integration_connections_org_provider_domain_status",
        table_name="integration_connections",
    )
    op.drop_index("ix_integration_connections_external_reference", table_name="integration_connections")
    op.drop_index("ix_integration_connections_status", table_name="integration_connections")
    op.drop_index("ix_integration_connections_domain", table_name="integration_connections")
    op.drop_index("ix_integration_connections_provider", table_name="integration_connections")
    op.drop_index("ix_integration_connections_org_id", table_name="integration_connections")
    op.drop_table("integration_connections")

    message_operation_status.drop(bind, checkfirst=True)
    provider_webhook_event_status.drop(bind, checkfirst=True)
    evidence_request_status.drop(bind, checkfirst=True)
    integration_operation_status.drop(bind, checkfirst=True)
    integration_connection_status.drop(bind, checkfirst=True)
