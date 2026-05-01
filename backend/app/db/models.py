"""SQLAlchemy database models."""

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import declarative_base

from app.domain.exports import EXPORT_PROGRESS_STAGES, EXPORT_STATUSES, EXPORT_TYPES
from app.security.permissions import Role

Base = declarative_base()


# ── Auth / multi-tenant models ─────────────────────────────────────


class Org(Base):
    """Organization (tenant)."""

    __tablename__ = "orgs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    legal_name = Column(Text, nullable=True)
    display_name = Column(Text, nullable=True)
    timezone = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    contacts_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    implementation_contact_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    logo_url = Column(Text, nullable=True)
    require_driver_ack = Column(Boolean, nullable=False, default=False)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    voice_enabled = Column(Boolean, nullable=False, default=False)
    safety_manager_phone = Column(Text, nullable=True)
    instruction_source = Column(Text, nullable=False, default="default")
    require_org_admin_mfa = Column(Boolean, nullable=False, default=False)


class User(Base):
    """Application user with hashed password and role."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default=Role.SAFETY_MANAGER.value)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_active = Column(Boolean, nullable=False, default=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret_hash = Column(Text, nullable=True)
    mfa_enrolled_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    mfa_last_challenged_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    mfa_disabled_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)


class UserOrg(Base):
    """Many-to-many link between users and organizations."""

    __tablename__ = "user_orgs"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        primary_key=True,
    )


class OrgUserInvite(Base):
    """Pending invite for a user to join an organization."""

    __tablename__ = "org_user_invites"

    invite_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(Text, nullable=False, index=True)
    role = Column(Text, nullable=False, default=Role.SAFETY_MANAGER.value)
    status = Column(Text, nullable=False, default="pending", index=True)
    invited_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference to inviter
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_sent_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    deactivated_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)


# ── Core domain models ─────────────────────────────────────────────


class Event(Base):
    """Append-only event log — source of truth. No updates, no deletes."""

    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True, index=True  # soft reference
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    event_type = Column(Text, nullable=False, index=True)
    occurred_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_events_org_incident", "org_id", "incident_id"),
        Index("ix_events_org_type_occurred", "org_id", "event_type", "occurred_at_utc"),
    )


class AuditEvent(Base):
    """Immutable audit trail for actor/org/incident/export/artifact actions."""

    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=False, index=True  # tenant root
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    export_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exports.export_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=False, index=True)
    action = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False, index=True)
    outcome = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    occurred_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    retention_expires_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    retention_purged_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_events_org_occurred", "org_id", "occurred_at_utc"),
        Index(
            "ix_audit_events_org_incident_occurred",
            "org_id",
            "incident_id",
            "occurred_at_utc",
        ),
        Index(
            "ix_audit_events_org_export_occurred",
            "org_id",
            "export_id",
            "occurred_at_utc",
        ),
        Index(
            "ix_audit_events_org_actor_occurred",
            "org_id",
            "actor_id",
            "occurred_at_utc",
        ),
        Index(
            "ix_audit_events_org_event_type_occurred",
            "org_id",
            "event_type",
            "occurred_at_utc",
        ),
    )


class Incident(Base):
    """Summary pointer for an incident."""

    __tablename__ = "incidents"

    incident_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root; nullable for legacy only
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    status = Column(
        Enum(
            "open",
            "evidence_capturing",
            "accident_occurred",
            "closed",
            name="incident_status",
        ),
        nullable=False,
        default="open",
    )
    adc_vehicle_id = Column(Text, nullable=True)
    samsara_vehicle_id = Column(Text, nullable=True)
    adc_driver_id = Column(Text, nullable=True)
    # Phase 2: nullable opaque trailer reference; matches trailer.adc_trailer_id.
    adc_trailer_id = Column(Text, nullable=True)
    severity = Column(Text, nullable=True)
    case_status = Column(
        Enum(
            "new",
            "in_review",
            "awaiting_evidence",
            "awaiting_follow_up",
            "ready_for_export",
            "exported",
            "escalated",
            "closed",
            name="incident_case_status",
        ),
        nullable=False,
        default="new",
        server_default="new",
    )
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # soft assignment
    owner_assigned_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    owner_assigned_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    team_queue = Column(Text, nullable=True)
    readiness_state = Column(Text, nullable=True)
    completeness_percent = Column(Integer, nullable=True)
    completeness_status = Column(Text, nullable=True)
    first_reviewed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    last_activity_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    ready_for_export_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    is_test_incident = Column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_incidents_org_case_status_owner",
            "org_id",
            "case_status",
            "owner_user_id",
        ),
        Index("ix_incidents_org_readiness_state", "org_id", "readiness_state"),
        Index("ix_incidents_org_updated_at_utc", "org_id", "updated_at_utc"),
        Index(
            "ix_incidents_org_last_activity_at_utc", "org_id", "last_activity_at_utc"
        ),
    )


class CaseNote(Base):
    """Internal-only case notes with edit and soft-delete metadata."""

    __tablename__ = "case_notes"

    note_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body = Column(Text, nullable=False)
    note_type = Column(
        Enum("standard", "tagged", "decision", name="case_note_type"),
        nullable=False,
        default="standard",
        server_default="standard",
    )
    tags_json = Column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    edited_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    edited_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    deleted_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    deleted_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    is_deleted = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_case_notes_org_incident_created",
            "org_id",
            "incident_id",
            "created_at_utc",
        ),
        Index(
            "ix_case_notes_org_incident_deleted_created",
            "org_id",
            "incident_id",
            "is_deleted",
            "created_at_utc",
        ),
    )


class CaseTask(Base):
    """Action items tracked for each case."""

    __tablename__ = "case_tasks"

    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(
        Enum(
            "review",
            "evidence",
            "follow_up",
            "export",
            "other",
            name="case_task_type",
        ),
        nullable=False,
        default="other",
        server_default="other",
    )
    status = Column(
        Enum(
            "open",
            "in_progress",
            "blocked",
            "completed",
            "canceled",
            name="case_task_status",
        ),
        nullable=False,
        default="open",
        server_default="open",
    )
    priority = Column(
        Enum("low", "medium", "high", "urgent", name="case_task_priority"),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    due_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    assigned_to_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft assignment
    )
    assigned_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    assigned_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    canceled_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    canceled_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    canceled_reason = Column(Text, nullable=True)
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_case_tasks_org_incident_status", "org_id", "incident_id", "status"),
        Index("ix_case_tasks_org_status_due_at_utc", "org_id", "status", "due_at_utc"),
    )


class CaseReadinessOverride(Base):
    """Manual readiness override snapshots for cases."""

    __tablename__ = "case_readiness_overrides"

    override_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    readiness_state = Column(Text, nullable=True)
    completeness_percent = Column(Integer, nullable=True)
    completeness_status = Column(Text, nullable=True)
    reason = Column(Text, nullable=False)
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    cleared_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    cleared_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_case_readiness_overrides_org_incident_created",
            "org_id",
            "incident_id",
            "created_at_utc",
        ),
    )


class Artifact(Base):
    """Metadata lookup for evidence artifacts."""

    __tablename__ = "artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type = Column(Text, nullable=False)
    status = Column(
        Enum("pending", "captured", "unavailable", name="artifact_status"),
        nullable=False,
        default="pending",
    )
    capture_window_start_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    capture_window_end_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    s3_bucket = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)
    sha256 = Column(Text, nullable=True)
    byte_size = Column(BigInteger, nullable=True)
    uploaded_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    unavailable_reason_code = Column(Text, nullable=True)
    unavailable_reason_detail = Column(Text, nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_artifacts_org_incident", "org_id", "incident_id"),
        Index("ix_artifacts_incident_type", "incident_id", "artifact_type"),
    )


class Export(Base):
    """Export request tracking."""

    __tablename__ = "exports"

    export_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=False, index=True  # tenant root
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_type = Column(
        Enum(*EXPORT_TYPES, name="export_type"),
        nullable=False,
        default="court_defense",
        server_default="court_defense",
    )
    profile_id = Column(
        Text,
        nullable=False,
        default="court_defense_v1",
        server_default="court_defense_v1",
    )
    requested_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    retry_parent_export_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exports.export_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # self-ref: deleting parent shouldn't cascade
    )
    options_json = Column(JSONB, nullable=False, default=dict)
    status = Column(
        Enum(*EXPORT_STATUSES, name="export_status"),
        nullable=False,
        default="requested",
        server_default="requested",
    )
    progress_stage = Column(
        Enum(*EXPORT_PROGRESS_STAGES, name="export_progress_stage"),
        nullable=False,
        default="request_accepted",
        server_default="request_accepted",
    )
    error_message = Column(Text, nullable=True)
    package_sha256 = Column(Text, nullable=True)
    byte_size = Column(BigInteger, nullable=True)
    artifact_count = Column(Integer, nullable=False, default=0, server_default="0")
    timeline_event_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    requested_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    processing_started_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    s3_bucket = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("ix_exports_org_incident", "org_id", "incident_id"),)


class IntegrationConnection(Base):
    """Provider integration connection configuration per org."""

    __tablename__ = "integration_connections"

    connection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider = Column(Text, nullable=False, index=True)
    domain = Column(Text, nullable=True, index=True)
    status = Column(
        Enum(
            "pending",
            "active",
            "inactive",
            "error",
            name="integration_connection_status",
        ),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    external_reference = Column(Text, nullable=True, index=True)
    credentials_ref = Column(Text, nullable=True)
    config_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    last_synced_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_integration_connections_org_provider_domain_status",
            "org_id",
            "provider",
            "domain",
            "status",
        ),
        Index(
            "ix_integration_connections_org_provider_updated",
            "org_id",
            "provider",
            "updated_at_utc",
        ),
    )


class IntegrationOperation(Base):
    """Operation execution state for external provider integrations."""

    __tablename__ = "integration_operations"

    operation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_connections.connection_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    provider = Column(Text, nullable=False, index=True)
    domain = Column(Text, nullable=True, index=True)
    operation_type = Column(Text, nullable=False, index=True)
    status = Column(
        Enum(
            "requested",
            "submitted_to_provider",
            "processing_at_provider",
            "available",
            "downloaded",
            "unavailable",
            "queued",
            "running",
            "succeeded",
            "failed",
            "canceled",
            name="integration_operation_status",
        ),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    correlation_id = Column(Text, nullable=True, index=True)
    external_reference = Column(Text, nullable=True, index=True)
    external_reference_id = Column(Text, nullable=True, index=True)
    payload_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    result_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_message = Column(Text, nullable=True)
    error_code = Column(Text, nullable=True, index=True)
    error_category = Column(Text, nullable=True, index=True)
    error_provider_key = Column(Text, nullable=True, index=True)
    error_retryable = Column(Boolean, nullable=True)
    error_user_facing_message = Column(Text, nullable=True)
    error_operator_message = Column(Text, nullable=True)
    requested_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_integration_operations_org_provider_domain_status_requested",
            "org_id",
            "provider",
            "domain",
            "status",
            "requested_at_utc",
        ),
        Index(
            "ix_integration_operations_org_incident_status",
            "org_id",
            "incident_id",
            "status",
        ),
    )


class IntegrationValidationResult(Base):
    """Persisted integration validation outcomes for org onboarding UX."""

    __tablename__ = "integration_validation_results"

    validation_result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_connections.connection_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    credential_status = Column(Text, nullable=False)
    capability_status = Column(Text, nullable=False)
    mapping_status = Column(Text, nullable=False)
    messages_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    validated_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IntegrationOperationStatusHistory(Base):
    """Append-only status transitions for integration operations."""

    __tablename__ = "integration_operation_status_history"

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_operations.operation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider = Column(Text, nullable=False, index=True)
    domain = Column(Text, nullable=True, index=True)
    from_status = Column(Text, nullable=True)
    to_status = Column(Text, nullable=False, index=True)
    correlation_id = Column(Text, nullable=True, index=True)
    external_reference = Column(Text, nullable=True, index=True)
    external_reference_id = Column(Text, nullable=True, index=True)
    message = Column(Text, nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_integration_op_history_org_provider_domain_to_status_created",
            "org_id",
            "provider",
            "domain",
            "to_status",
            "created_at_utc",
        ),
        Index(
            "ix_integration_op_history_org_incident_created",
            "org_id",
            "incident_id",
            "created_at_utc",
        ),
    )


class EvidenceRequest(Base):
    """External evidence request state per incident/provider."""

    __tablename__ = "evidence_requests"

    evidence_request_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    operation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_operations.operation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    provider = Column(Text, nullable=False, index=True)
    domain = Column(Text, nullable=True, index=True)
    status = Column(
        Enum(
            "open",
            "in_progress",
            "fulfilled",
            "failed",
            "canceled",
            name="evidence_request_status",
        ),
        nullable=False,
        default="open",
        server_default="open",
        index=True,
    )
    correlation_id = Column(Text, nullable=True, index=True)
    external_reference = Column(Text, nullable=True, index=True)
    request_payload_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    response_payload_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_code = Column(Text, nullable=True, index=True)
    error_category = Column(Text, nullable=True, index=True)
    error_provider_key = Column(Text, nullable=True, index=True)
    error_retryable = Column(Boolean, nullable=True)
    error_user_facing_message = Column(Text, nullable=True)
    error_operator_message = Column(Text, nullable=True)
    requested_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    due_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    fulfilled_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_evidence_requests_org_provider_domain_status_requested",
            "org_id",
            "provider",
            "domain",
            "status",
            "requested_at_utc",
        ),
        Index(
            "ix_evidence_requests_org_incident_status",
            "org_id",
            "incident_id",
            "status",
        ),
    )


class ExternalMapping(Base):
    """Cross-reference between internal ids and provider external ids."""

    __tablename__ = "external_mappings"

    mapping_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider = Column(Text, nullable=False, index=True)
    domain = Column(Text, nullable=True, index=True)
    internal_entity_type = Column(Text, nullable=False, index=True)
    internal_entity_id = Column(Text, nullable=False, index=True)
    external_reference = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, default="active", server_default="active")
    metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_external_mappings_org_provider_domain_entity",
            "org_id",
            "provider",
            "domain",
            "internal_entity_type",
            "internal_entity_id",
        ),
        Index(
            "ix_external_mappings_org_provider_external_ref",
            "org_id",
            "provider",
            "external_reference",
        ),
        Index("ix_external_mappings_org_incident", "org_id", "incident_id"),
    )


class ProviderWebhookEvent(Base):
    """Inbound provider webhook events for processing and replay."""

    __tablename__ = "provider_webhook_events"

    webhook_event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider = Column(Text, nullable=False, index=True)
    domain = Column(Text, nullable=True, index=True)
    event_type = Column(Text, nullable=False, index=True)
    status = Column(
        Enum(
            "received",
            "processed",
            "ignored",
            "failed",
            name="provider_webhook_event_status",
        ),
        nullable=False,
        default="received",
        server_default="received",
        index=True,
    )
    signature_valid = Column(Boolean, nullable=True, index=True)
    idempotency_key = Column(Text, nullable=True, index=True)
    processing_outcome = Column(Text, nullable=True, index=True)
    correlation_id = Column(Text, nullable=True, index=True)
    external_reference = Column(Text, nullable=True, index=True)
    raw_payload = Column(Text, nullable=False, default="", server_default="")
    payload_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_details_json = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    error_message = Column(Text, nullable=True)
    received_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_provider_webhook_events_org_provider_domain_status_received",
            "org_id",
            "provider",
            "domain",
            "status",
            "received_at_utc",
        ),
        Index(
            "ix_provider_webhook_events_org_incident_received",
            "org_id",
            "incident_id",
            "received_at_utc",
        ),
    )


class MessageOperation(Base):
    """Message send/receive operations, optionally tied to integration operations."""

    __tablename__ = "message_operations"

    message_operation_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_operations.operation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider = Column(Text, nullable=False, index=True)
    purpose = Column(Text, nullable=False, server_default="notification", index=True)
    to_e164 = Column(Text, nullable=True, index=True)
    provider_message_id = Column(Text, nullable=True, index=True)
    normalized_error_code = Column(Text, nullable=True, index=True)
    domain = Column(Text, nullable=True, index=True)
    channel = Column(Text, nullable=True, index=True)
    direction = Column(Text, nullable=True, index=True)
    status = Column(
        Enum(
            "queued",
            "sent",
            "delivered",
            "undelivered",
            "failed",
            "received",
            name="message_operation_status",
        ),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    correlation_id = Column(Text, nullable=True, index=True)
    external_reference = Column(Text, nullable=True, index=True)
    template_name = Column(Text, nullable=True)
    payload_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    sent_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    delivered_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_message_operations_org_provider_domain_status_created",
            "org_id",
            "provider",
            "domain",
            "status",
            "created_at_utc",
        ),
        Index(
            "ix_message_operations_org_incident_created",
            "org_id",
            "incident_id",
            "created_at_utc",
        ),
    )


class MessageOperationStatusHistory(Base):
    """Timeline of status transitions for a message operation."""

    __tablename__ = "message_operation_status_history"

    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_operation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message_operations.message_operation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status = Column(Text, nullable=True)
    to_status = Column(Text, nullable=False, index=True)
    provider_message_id = Column(Text, nullable=True, index=True)
    normalized_error_code = Column(Text, nullable=True, index=True)
    details_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class SessionRecord(Base):
    """Server-side authenticated session state."""

    __tablename__ = "sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Identifies the principal of a non-user session (e.g. a driver). For web
    # sessions this is left NULL because ``user_id`` already carries the subject.
    subject_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    client_type = Column(Text, nullable=False)
    device_descriptor = Column(Text, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    refresh_family_id = Column(UUID(as_uuid=True), nullable=False, index=True)


class RefreshToken(Base):
    """Refresh token lineage bound to a session."""

    __tablename__ = "refresh_tokens"

    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    parent_token_id = Column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.token_id", ondelete="CASCADE"), nullable=True  # self-ref: cascade revokes descendants
    )
    token_hash = Column(Text, nullable=False, unique=True, index=True)
    issued_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    consumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)


class JobExecutionMeta(Base):
    """Persistent per-task execution metadata for operations visibility."""

    __tablename__ = "job_execution_meta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    celery_task_id = Column(Text, nullable=False, unique=True, index=True)
    task_name = Column(Text, nullable=False, index=True)
    task_type = Column(Text, nullable=False, index=True)
    status = Column(
        Enum(
            "queued",
            "running",
            "retrying",
            "failed",
            "succeeded",
            "stuck",
            name="job_execution_status",
        ),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=True)
    retry_category = Column(Text, nullable=True, index=True)
    should_retry = Column(Boolean, nullable=True)
    next_retry_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    started_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    last_heartbeat_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    args_json = Column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    kwargs_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ── Onboarding readiness models ──────────────────────────────────────


class OrgLaunchReadinessSnapshot(Base):
    """Point-in-time launch readiness snapshot for an organization."""

    __tablename__ = "org_launch_readiness_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(
        Enum(
            "not_started",
            "in_progress",
            "pilot_ready",
            "launch_ready",
            "blocked",
            name="org_launch_readiness_status",
        ),
        nullable=False,
        default="not_started",
        server_default="not_started",
    )
    percent_complete = Column(Integer, nullable=False, default=0, server_default="0")
    summary_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_org_launch_readiness_snapshots_org_created",
            "org_id",
            "created_at_utc",
        ),
    )


class OrgLaunchReadinessStepProgress(Base):
    """Step-level progress for an onboarding readiness snapshot."""

    __tablename__ = "org_launch_readiness_step_progress"

    step_progress_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("org_launch_readiness_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key = Column(Text, nullable=False)
    step_label = Column(Text, nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(
        Enum(
            "not_started",
            "in_progress",
            "completed",
            "blocked",
            name="org_launch_readiness_step_status",
        ),
        nullable=False,
        default="not_started",
        server_default="not_started",
    )
    metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_org_launch_readiness_steps_org_snapshot",
            "org_id",
            "snapshot_id",
            "step_order",
        ),
    )


class OrgLaunchReadinessBlocker(Base):
    """Blockers linked to a readiness snapshot and optionally a specific step."""

    __tablename__ = "org_launch_readiness_blockers"

    blocker_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("org_launch_readiness_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    detail = Column(Text, nullable=False)
    severity = Column(
        Enum("info", "warning", "error", name="org_launch_readiness_blocker_severity"),
        nullable=False,
        default="warning",
        server_default="warning",
    )
    blocking_step_key = Column(Text, nullable=True)
    is_resolved = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    resolved_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_org_launch_readiness_blockers_org_snapshot",
            "org_id",
            "snapshot_id",
            "is_resolved",
        ),
    )


class OrgOnboardingStepCompletion(Base):
    """Latest persisted completion metadata for each onboarding step."""

    __tablename__ = "org_onboarding_step_completions"

    completion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key = Column(Text, nullable=False)
    is_completed = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    completed_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    completion_source = Column(Text, nullable=True)
    updated_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_org_onboarding_step_completion_org_step",
            "org_id",
            "step_key",
            unique=True,
        ),
    )


class OrgTestIncidentRun(Base):
    """Persisted test-incident run metadata for onboarding/admin validation."""

    __tablename__ = "org_test_incident_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=True, index=True
    )
    status = Column(
        Enum(
            "not_started",
            "in_progress",
            "completed",
            "blocked",
            name="org_test_incident_run_status",
        ),
        nullable=False,
        default="in_progress",
        server_default="in_progress",
    )
    step_results_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    findings_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    started_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_org_test_incident_runs_org_started", "org_id", "started_at_utc"),
    )


class OrgExportValidationRun(Base):
    """Persisted onboarding export validation runs for launch-readiness checks."""

    __tablename__ = "org_export_validation_runs"

    validation_run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=True, index=True
    )
    export_id = Column(
        UUID(as_uuid=True), ForeignKey("exports.export_id", ondelete="CASCADE"), nullable=True, index=True
    )
    status = Column(
        Enum(
            "passed",
            "failed",
            name="org_export_validation_run_status",
        ),
        nullable=False,
        default="failed",
        server_default="failed",
        index=True,
    )
    results_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    warnings_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    missing_items_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    validated_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_org_export_validation_runs_org_validated",
            "org_id",
            "validated_at_utc",
        ),
    )


class OrgPlanEntitlement(Base):
    """Organization plan and entitlement state."""

    __tablename__ = "org_plan_entitlements"

    entitlement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_code = Column(Text, nullable=False, default="starter", server_default="starter")
    billing_status = Column(
        Text, nullable=False, default="active", server_default="active"
    )
    core_incident_protocol = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    entitlements_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    effective_from_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    effective_to_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_org_plan_entitlements_org_current", "org_id", "effective_to_utc"),
    )


class DemoScenario(Base):
    """Curated demo scenarios, optionally seeded for an organization."""

    __tablename__ = "demo_scenarios"

    scenario_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_key = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    seeded_by = Column(Text, nullable=True)
    seed_batch_id = Column(Text, nullable=True)
    seed_metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_demo_scenarios_org_key", "org_id", "scenario_key", unique=True),
        Index("ix_demo_scenarios_org_active", "org_id", "is_active"),
    )


class HelpCategory(Base):
    """Knowledge base category metadata."""

    __tablename__ = "help_categories"

    category_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default=text("0"))
    metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    is_published = Column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    published_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    unpublished_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_help_categories_org_slug", "org_id", "slug", unique=True),
        Index("ix_help_categories_org_published", "org_id", "is_published", "sort_order"),
    )


class HelpArticle(Base):
    """Help center article content and publication metadata."""

    __tablename__ = "help_articles"

    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("help_categories.category_id", ondelete="SET NULL"), nullable=True, index=True  # soft reference
    )
    slug = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    body_markdown = Column(Text, nullable=False)
    metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    is_published = Column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    published_at_utc = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    unpublished_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    updated_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_help_articles_org_slug", "org_id", "slug", unique=True),
        Index(
            "ix_help_articles_org_published_category",
            "org_id",
            "is_published",
            "category_id",
            "published_at_utc",
        ),
    )


class TrustSection(Base):
    """Trust center section content and publication metadata."""

    __tablename__ = "trust_sections"

    section_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    body_markdown = Column(Text, nullable=False)
    metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    sort_order = Column(Integer, nullable=False, default=0, server_default=text("0"))
    is_published = Column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    published_at_utc = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    unpublished_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_trust_sections_org_slug", "org_id", "slug", unique=True),
        Index(
            "ix_trust_sections_org_published_sort",
            "org_id",
            "is_published",
            "sort_order",
            "published_at_utc",
        ),
    )


class DeploymentScopeSnapshot(Base):
    """Point-in-time deployment scope snapshot for an organization."""

    __tablename__ = "deployment_scope_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_version = Column(Text, nullable=False)
    scope_json = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'"))
    captured_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    captured_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_deployment_scope_snapshots_org_captured",
            "org_id",
            "captured_at_utc",
        ),
    )


class HelpArticleView(Base):
    """Per-view telemetry events for help article usage."""

    __tablename__ = "help_article_views"

    view_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id = Column(
        UUID(as_uuid=True), ForeignKey("help_articles.article_id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewer_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True  # soft reference
    )
    source = Column(Text, nullable=True)
    metadata_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    viewed_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index(
            "ix_help_article_views_org_article_viewed",
            "org_id",
            "article_id",
            "viewed_at_utc",
        ),
    )


class ExpansionReadinessSnapshot(Base):
    """Optional cached expansion readiness summary per org and scope."""

    __tablename__ = "expansion_readiness_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_key = Column(Text, nullable=False)
    readiness_score = Column(Integer, nullable=True)
    status = Column(Text, nullable=False, default="unknown", server_default="unknown")
    summary_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    computed_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_expansion_readiness_snapshots_org_scope",
            "org_id",
            "scope_key",
            unique=True,
        ),
        Index(
            "ix_expansion_readiness_snapshots_org_computed",
            "org_id",
            "computed_at_utc",
        ),
    )


# ── Driver protocol models ────────────────────────────────────────────


class Driver(Base):
    """Driver profile for communications and assignments."""

    __tablename__ = "drivers"

    driver_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_e164 = Column(Text, nullable=False, unique=True, index=True)
    display_name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class OtpChallenge(Base):
    """One-time password challenge tracking."""

    __tablename__ = "otp_challenges"

    challenge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_e164 = Column(Text, nullable=False, index=True)
    otp_code_hash = Column(Text, nullable=False)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at_utc = Column(TIMESTAMP(timezone=True), nullable=False)
    attempt_count = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum("pending", "verified", "expired", "locked", name="otp_challenge_status"),
        nullable=False,
        default="pending",
    )
    twilio_sid = Column(Text, nullable=True)
    last_sent_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)


class DriverVehicleAssignment(Base):
    """Assignment of a driver to a vehicle."""

    __tablename__ = "driver_vehicle_assignments"

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id = Column(
        UUID(as_uuid=True), ForeignKey("drivers.driver_id", ondelete="CASCADE"), nullable=False, index=True
    )
    adc_vehicle_id = Column(Text, nullable=False, index=True)
    assigned_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    unassigned_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    source = Column(
        Enum("tms", "eld", "manual", "driver_app", name="driver_assignment_source"),
        nullable=False,
    )


class OrgVehicleRegistry(Base):
    """Organization vehicle records imported from provider feeds and CSV uploads."""

    __tablename__ = "org_vehicle_registry"

    vehicle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_number = Column(Text, nullable=False)
    vin = Column(Text, nullable=True)
    provider = Column(Text, nullable=True)
    provider_vehicle_id = Column(Text, nullable=True)
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    qr_deployment_status = Column(
        Enum(
            "not_generated",
            "generated",
            "distributed",
            "confirmed",
            name="vehicle_qr_deployment_status",
        ),
        nullable=False,
        default="not_generated",
        server_default="not_generated",
        index=True,
    )
    qr_generated_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    qr_distributed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    qr_confirmed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_org_vehicle_registry_org_unit", "org_id", "unit_number", unique=True),
        Index(
            "ix_org_vehicle_registry_org_provider_ext",
            "org_id",
            "provider",
            "provider_vehicle_id",
        ),
    )


class VehicleImportJob(Base):
    """Asynchronous vehicle import job state and review summary."""

    __tablename__ = "vehicle_import_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider = Column(Text, nullable=False)
    status = Column(
        Enum(
            "pending",
            "running",
            "succeeded",
            "failed",
            name="vehicle_import_job_status",
        ),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    records_total = Column(Integer, nullable=False, default=0, server_default=text("0"))
    records_processed = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_imported = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_updated = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_skipped = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_errored = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    warnings_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    outcomes_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    summary_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_message = Column(Text, nullable=True)
    started_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DriverImportJob(Base):
    """Asynchronous driver import job state and review summary."""

    __tablename__ = "driver_import_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider = Column(Text, nullable=False)
    status = Column(
        Enum(
            "pending", "running", "succeeded", "failed", name="driver_import_job_status"
        ),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    records_total = Column(Integer, nullable=False, default=0, server_default=text("0"))
    records_processed = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_imported = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_updated = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_skipped = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_errored = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    warnings_json = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    outcomes_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    summary_json = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_message = Column(Text, nullable=True)
    started_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class VehicleQrToken(Base):
    """Vehicle QR tokens for driver app onboarding."""

    __tablename__ = "vehicle_qr_tokens"

    qr_token = Column(Text, primary_key=True)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    adc_vehicle_id = Column(Text, nullable=False, index=True)
    status = Column(
        Enum("active", "revoked", "rotated", name="vehicle_qr_token_status"),
        nullable=False,
        default="active",
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    rotated_from_token = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_vehicle_qr_tokens_active_vehicle",
            "adc_vehicle_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )


class DriverInstructionSet(Base):
    """Group of driver instructions by scope."""

    __tablename__ = "driver_instruction_sets"

    instruction_set_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope = Column(
        Enum("default", "company", "insurer", name="driver_instruction_scope"),
        nullable=False,
        default="default",
    )
    require_ack = Column(Boolean, nullable=False, default=False)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class DriverInstructionStep(Base):
    """Steps belonging to a driver instruction set."""

    __tablename__ = "driver_instruction_steps"

    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instruction_set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("driver_instruction_sets.instruction_set_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order = Column("order", Integer, nullable=False, quote=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)


# ── Crash-packet notification (Phase 1 of demo workflow) ───────────


class OrgNotificationRecipient(Base):
    """Per-org control file of recipients for crash packet notifications.

    Acts as the single source of truth for who receives what channel
    (email today; sms/voice can read this table in a later phase).
    """

    __tablename__ = "org_notification_recipients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = Column(Text, nullable=False)
    full_name = Column(Text, nullable=True)
    role_tag = Column(Text, nullable=True)
    # JSON array of channel strings: ["email"], ["email","sms"], etc.
    channels = Column(
        JSONB, nullable=False, default=list, server_default=text("'[\"email\"]'")
    )
    active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_org_notification_recipients_org_active",
            "org_id",
            "active",
        ),
    )


class CrashPacketDelivery(Base):
    """Tracks one crash-packet send attempt for an incident.

    Indexed by incident_id for idempotency and by status/dispatched_at
    for the SLA watchdog scan.
    """

    __tablename__ = "crash_packet_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(
            "queued",
            "dispatched",
            "sent",
            "partial",
            "failed",
            "overdue",
            name="crash_packet_delivery_status",
        ),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    target_sla_seconds = Column(Integer, nullable=False, default=900)
    idempotency_key = Column(Text, nullable=False, unique=True)
    payload_hash = Column(Text, nullable=True)
    sent_to = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    failed_to = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    message_ids = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    error_summary = Column(Text, nullable=True)
    dispatched_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    delivered_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_crash_packet_deliveries_status_dispatched",
            "status",
            "dispatched_at_utc",
        ),
    )


# ── TMS-cached trailer + maintenance + connection metadata (Phase 2) ──


class Trailer(Base):
    """A trailer record, either entered manually or synced from a TMS."""

    __tablename__ = "trailers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Stable per-org opaque id matching incident.adc_trailer_id.
    adc_trailer_id = Column(Text, nullable=False)
    vin = Column(Text, nullable=True)
    make = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    plate = Column(Text, nullable=True)
    last_inspection_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    source = Column(
        Enum("manual", "tms", name="trailer_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    # External id from the source-of-truth TMS (used as upsert key with org_id).
    external_id = Column(Text, nullable=True)
    synced_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_trailers_org_adc_trailer_id", "org_id", "adc_trailer_id", unique=True),
        Index("ix_trailers_org_external_id", "org_id", "external_id"),
    )


class MaintenanceRecord(Base):
    """A single maintenance event for a tractor or trailer.

    Indexed on ``(org_id, asset_kind, asset_id, performed_at_utc desc)`` for
    the canonical 1-year lookup.
    """

    __tablename__ = "maintenance_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_kind = Column(
        Enum("tractor", "trailer", name="maintenance_asset_kind"),
        nullable=False,
    )
    # Free-form per-org asset id: tractor unit_number or trailer.adc_trailer_id.
    asset_id = Column(Text, nullable=False)
    performed_at_utc = Column(TIMESTAMP(timezone=True), nullable=False)
    vendor = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    mileage = Column(Integer, nullable=True)
    doc_artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )
    source = Column(
        Enum("manual", "tms", name="maintenance_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    external_id = Column(Text, nullable=True)
    synced_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_maintenance_records_lookup",
            "org_id",
            "asset_kind",
            "asset_id",
            "performed_at_utc",
        ),
        Index(
            "ix_maintenance_records_external_id",
            "org_id",
            "external_id",
            unique=False,
        ),
    )


class TmsConnection(Base):
    """Per-org configuration for an ODBC-based TMS data source."""

    __tablename__ = "tms_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(Text, nullable=False)
    vendor_hint = Column(
        Enum(
            "mcleod",
            "tmw",
            "fleetio",
            "whip_around",
            "generic",
            name="tms_vendor_hint",
        ),
        nullable=False,
        default="generic",
        server_default="generic",
    )
    # Reference key into SECRET_PROVIDER (e.g. AWS Secrets Manager). The
    # actual ODBC DSN / connection string is *never* stored in the DB.
    odbc_secret_ref = Column(Text, nullable=False)
    schedule_cron = Column(
        Text, nullable=False, default="0 3 * * *", server_default="0 3 * * *"
    )
    last_synced_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    status = Column(
        Enum("active", "disabled", "error", name="tms_connection_status"),
        nullable=False,
        default="active",
        server_default="active",
    )
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = ()


class TmsFieldMap(Base):
    """A single source-column → target-field mapping for a TMS connection."""

    __tablename__ = "tms_field_maps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tms_connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tms_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity = Column(
        Enum("trailer", "maintenance_record", name="tms_field_map_entity"),
        nullable=False,
    )
    source_table = Column(Text, nullable=False)
    source_column = Column(Text, nullable=False)
    target_field = Column(Text, nullable=False)
    transform = Column(
        Text, nullable=False, default="none", server_default="none"
    )
    is_key = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_tms_field_maps_conn_entity",
            "tms_connection_id",
            "entity",
        ),
    )
