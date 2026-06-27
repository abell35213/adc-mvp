"""SQLAlchemy database models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.exports import EXPORT_PROGRESS_STAGES, EXPORT_STATUSES, EXPORT_TYPES
from app.security.permissions import Role


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


# ── Auth / multi-tenant models ─────────────────────────────────────


class Org(Base):
    """Organization (tenant)."""

    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    legal_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    contacts_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    implementation_contact_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    require_driver_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_manager_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    instruction_source: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    require_org_admin_mfa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Carrier identity for the FMCSA MCMIS pull (single carrier per tenant).
    usdot_number: Mapped[str | None] = mapped_column(Text, nullable=True)


class User(Base):
    """Application user with hashed password and role."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default=Role.SAFETY_MANAGER.value)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enrolled_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    mfa_last_challenged_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    mfa_disabled_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class UserOrg(Base):
    """Many-to-many link between users and organizations."""

    __tablename__ = "user_orgs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        primary_key=True,
    )


class OrgUserInvite(Base):
    """Pending invite for a user to join an organization."""

    __tablename__ = "org_user_invites"

    invite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default=Role.SAFETY_MANAGER.value)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", index=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference to inviter
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_sent_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    deactivated_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


# ── Core domain models ─────────────────────────────────────────────


class Event(Base):
    """Append-only event log — source of truth. No updates, no deletes."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True, index=True  # soft reference
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    occurred_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_events_org_incident", "org_id", "incident_id"),
        Index("ix_events_org_type_occurred", "org_id", "event_type", "occurred_at_utc"),
    )


class AuditEvent(Base):
    """Immutable audit trail for actor/org/incident/export/artifact actions."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=False, index=True  # tenant root
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    export_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exports.export_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    occurred_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    retention_expires_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    retention_purged_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
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

    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root; nullable for legacy only
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
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
    adc_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    samsara_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    adc_driver_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 2: nullable opaque trailer reference; matches trailer.adc_trailer_id.
    adc_trailer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_status: Mapped[str] = mapped_column(
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
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # soft assignment
    owner_assigned_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    owner_assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    team_queue: Mapped[str | None] = mapped_column(Text, nullable=True)
    readiness_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completeness_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_reviewed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_activity_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ready_for_export_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    is_test_incident: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(
        Enum("standard", "tagged", "decision", name="case_note_type"),
        nullable=False,
        default="standard",
        server_default="standard",
    )
    tags_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    edited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    edited_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
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
    status: Mapped[str] = mapped_column(
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
    priority: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "urgent", name="case_task_priority"),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    due_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft assignment
    )
    assigned_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    canceled_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    canceled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    override_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    readiness_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completeness_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    cleared_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    cleared_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=True, index=True  # tenant root
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "captured", "unavailable", name="artifact_status"),
        nullable=False,
        default="pending",
    )
    capture_window_start_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    capture_window_end_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    unavailable_reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    unavailable_reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Many-to-one link from a dock photo (or, when the imaging-integration
    # follow-on project lands, a digitized weigh ticket / dispatch sheet) to
    # a :class:`LoadingDockReport`. Nullable + indexed so existing artifact
    # queries are unaffected.
    loading_dock_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loading_dock_reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_artifacts_org_incident", "org_id", "incident_id"),
        Index("ix_artifacts_incident_type", "incident_id", "artifact_type"),
    )


class Export(Base):
    """Export request tracking."""

    __tablename__ = "exports"

    export_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="RESTRICT"), nullable=False, index=True  # tenant root
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_type: Mapped[str] = mapped_column(
        Enum(*EXPORT_TYPES, name="export_type"),
        nullable=False,
        default="court_defense",
        server_default="court_defense",
    )
    profile_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="court_defense_v1",
        server_default="court_defense_v1",
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    retry_parent_export_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exports.export_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # self-ref: deleting parent shouldn't cascade
    )
    options_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        Enum(*EXPORT_STATUSES, name="export_status"),
        nullable=False,
        default="requested",
        server_default="requested",
    )
    progress_stage: Mapped[str] = mapped_column(
        Enum(*EXPORT_PROGRESS_STAGES, name="export_progress_stage"),
        nullable=False,
        default="request_accepted",
        server_default="request_accepted",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    timeline_event_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    requested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    processing_started_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    expires_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("ix_exports_org_incident", "org_id", "incident_id"),)


class IntegrationConnection(Base):
    """Provider integration connection configuration per org."""

    __tablename__ = "integration_connections"

    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
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
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    credentials_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    last_synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_connections.connection_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
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
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    result_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    error_provider_key: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_user_facing_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_operator_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    validation_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_connections.connection_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    credential_status: Mapped[str] = mapped_column(Text, nullable=False)
    capability_status: Mapped[str] = mapped_column(Text, nullable=False)
    mapping_status: Mapped[str] = mapped_column(Text, nullable=False)
    messages_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    validated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IntegrationOperationStatusHistory(Base):
    """Append-only status transitions for integration operations."""

    __tablename__ = "integration_operation_status_history"

    history_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_operations.operation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
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

    evidence_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_operations.operation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
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
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    request_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    response_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    error_provider_key: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_user_facing_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_operator_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    due_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    fulfilled_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    mapping_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    internal_entity_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    internal_entity_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    external_reference: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default="active")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    webhook_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
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
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    processing_outcome: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
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

    message_operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_operations.operation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # soft reference
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, server_default="notification", index=True)
    to_e164: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    normalized_error_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    direction: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
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
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    template_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    sent_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    delivered_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    history_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("message_operations.message_operation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    normalized_error_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class SessionRecord(Base):
    """Server-side authenticated session state."""

    __tablename__ = "sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Identifies the principal of a non-user session (e.g. a driver). For web
    # sessions this is left NULL because ``user_id`` already carries the subject.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    client_type: Mapped[str] = mapped_column(Text, nullable=False)
    device_descriptor: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    refresh_family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)


class RefreshToken(Base):
    """Refresh token lineage bound to a session."""

    __tablename__ = "refresh_tokens"

    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    parent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.token_id", ondelete="CASCADE"), nullable=True  # self-ref: cascade revokes descendants
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    consumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class JobExecutionMeta(Base):
    """Persistent per-task execution metadata for operations visibility."""

    __tablename__ = "job_execution_meta"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    celery_task_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    task_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
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
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_retries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_category: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    should_retry: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    next_retry_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    started_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_heartbeat_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    args_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    kwargs_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ── Onboarding readiness models ──────────────────────────────────────


class OrgLaunchReadinessSnapshot(Base):
    """Point-in-time launch readiness snapshot for an organization."""

    __tablename__ = "org_launch_readiness_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
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
    percent_complete: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc: Mapped[datetime] = mapped_column(
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

    step_progress_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_launch_readiness_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    step_label: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
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
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    blocker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_launch_readiness_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        Enum("info", "warning", "error", name="org_launch_readiness_blocker_severity"),
        nullable=False,
        default="warning",
        server_default="warning",
    )
    blocking_step_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    resolved_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
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

    completion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completion_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
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
    step_results_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    findings_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    started_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    validation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=True, index=True
    )
    export_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exports.export_id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
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
    results_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    warnings_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    missing_items_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    validated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc: Mapped[datetime] = mapped_column(
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

    entitlement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_code: Mapped[str] = mapped_column(Text, nullable=False, default="starter", server_default="starter")
    billing_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="active", server_default="active"
    )
    core_incident_protocol: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    entitlements_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    effective_from_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    effective_to_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    scenario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    seeded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_batch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    published_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    unpublished_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("help_categories.category_id", ondelete="SET NULL"), nullable=True, index=True  # soft reference
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    published_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    unpublished_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    published_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    unpublished_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_version: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'"))
    captured_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True  # soft reference
    )
    captured_at_utc: Mapped[datetime] = mapped_column(
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

    view_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("help_articles.article_id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True  # soft reference
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    viewed_at_utc: Mapped[datetime] = mapped_column(
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

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_key: Mapped[str] = mapped_column(Text, nullable=False)
    readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="unknown", server_default="unknown")
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    computed_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_e164: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class OtpChallenge(Base):
    """One-time password challenge tracking."""

    __tablename__ = "otp_challenges"

    challenge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_e164: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    otp_code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        Enum("pending", "verified", "expired", "locked", name="otp_challenge_status"),
        nullable=False,
        default="pending",
    )
    twilio_sid: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sent_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class DriverVehicleAssignment(Base):
    """Assignment of a driver to a vehicle."""

    __tablename__ = "driver_vehicle_assignments"

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drivers.driver_id", ondelete="CASCADE"), nullable=False, index=True
    )
    adc_vehicle_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    assigned_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    unassigned_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(
        Enum("tms", "eld", "manual", "driver_app", name="driver_assignment_source"),
        nullable=False,
    )


class OrgVehicleRegistry(Base):
    """Organization vehicle records imported from provider feeds and CSV uploads."""

    __tablename__ = "org_vehicle_registry"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_number: Mapped[str] = mapped_column(Text, nullable=False)
    vin: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    qr_deployment_status: Mapped[str] = mapped_column(
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
    qr_generated_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    qr_distributed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    qr_confirmed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    license_plate: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    dot_unit_type: Mapped[str | None] = mapped_column(
        Enum("tractor", "straight_truck", "other", name="dot_unit_type"),
        nullable=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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
        Index(
            "ix_org_vehicle_registry_org_plate_state",
            "org_id",
            "license_plate",
            "license_state",
        ),
    )


class VehicleImportJob(Base):
    """Asynchronous vehicle import job state and review summary."""

    __tablename__ = "vehicle_import_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
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
    records_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    records_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_imported: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_errored: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    warnings_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    outcomes_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DriverImportJob(Base):
    """Asynchronous driver import job state and review summary."""

    __tablename__ = "driver_import_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending", "running", "succeeded", "failed", name="driver_import_job_status"
        ),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    records_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    records_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_imported: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    records_errored: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    warnings_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    outcomes_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class VehicleQrToken(Base):
    """Vehicle QR tokens for driver app onboarding."""

    __tablename__ = "vehicle_qr_tokens"

    qr_token: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    adc_vehicle_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "revoked", "rotated", name="vehicle_qr_token_status"),
        nullable=False,
        default="active",
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    rotated_from_token: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    instruction_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(
        Enum("default", "company", "insurer", name="driver_instruction_scope"),
        nullable=False,
        default="default",
    )
    require_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class DriverInstructionStep(Base):
    """Steps belonging to a driver instruction set."""

    __tablename__ = "driver_instruction_steps"

    step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instruction_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driver_instruction_sets.instruction_set_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column("order", Integer, nullable=False, quote=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ── Crash-packet notification (Phase 1 of demo workflow) ───────────


class OrgNotificationRecipient(Base):
    """Per-org control file of recipients for crash packet notifications.

    Acts as the single source of truth for who receives what channel
    (email today; sms/voice can read this table in a later phase).
    """

    __tablename__ = "org_notification_recipients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON array of channel strings: ["email"], ["email","sms"], etc.
    channels: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[\"email\"]'")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
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
    target_sla_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    payload_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_to: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    failed_to: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    message_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at_utc: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    delivered_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Stable per-org opaque id matching incident.adc_trailer_id.
    adc_trailer_id: Mapped[str] = mapped_column(Text, nullable=False)
    vin: Mapped[str | None] = mapped_column(Text, nullable=True)
    make: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plate: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_inspection_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(
        Enum("manual", "tms", name="trailer_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    # External id from the source-of-truth TMS (used as upsert key with org_id).
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_kind: Mapped[str] = mapped_column(
        Enum("tractor", "trailer", name="maintenance_asset_kind"),
        nullable=False,
    )
    # Free-form per-org asset id: tractor unit_number or trailer.adc_trailer_id.
    asset_id: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doc_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        Enum("manual", "tms", name="maintenance_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
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


# ── Dispatch instructions, weigh tickets, loading dock reports (Phase 3) ──
#
# These three tables follow the same TMS-cache pattern as Trailer/MaintenanceRecord:
# ``(org_id, external_id)`` upsert key, ``source`` enum of ``manual``/``tms``,
# ``synced_at_utc`` stamp, and indexes for the canonical crash-packet lookups.
# All three are linked to incidents either via a direct ``incident_id`` FK or
# via the trip-context fallback (driver / vehicle / trailer + 24h window) in
# ``app.services.crash_packet_query``.


class DispatchInstruction(Base):
    """Trip dispatch handed to the driver — paper or TMS-recorded."""

    __tablename__ = "dispatch_instructions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Linkage — opaque per-org ids, like Trailer/Incident.
    adc_driver_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    adc_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    adc_trailer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Trip identity.
    dispatch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    load_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Times.
    dispatched_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    pickup_appointment_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    delivery_appointment_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    eta_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Locations (free text — not a structured address — matches paper dispatch).
    origin_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Compliance fields used by the crash brief callouts.
    hos_remaining_drive_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hos_remaining_duty_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forced_dispatch_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source plumbing.
    source: Mapped[str] = mapped_column(
        Enum("manual", "tms", name="dispatch_instruction_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_dispatch_instructions_org_driver_dispatched",
            "org_id",
            "adc_driver_id",
            "dispatched_at_utc",
        ),
        Index(
            "ix_dispatch_instructions_org_external_id",
            "org_id",
            "external_id",
            unique=True,
        ),
        Index(
            "ix_dispatch_instructions_org_incident",
            "org_id",
            "incident_id",
        ),
    )


class WeighStationReport(Base):
    """A weigh-ticket entry — paper-entered or TMS-recorded.

    External weigh-feed integrations (FMCSA SAFER, PrePass) and TMS imaging
    products are intentionally out of scope here; they will plug into this
    same table in a follow-on project (the ``source`` enum can grow to
    include ``external_feed``).
    """

    __tablename__ = "weigh_station_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adc_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    adc_trailer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_instruction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dispatch_instructions.id", ondelete="SET NULL"),
        nullable=True,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="SET NULL"),
        nullable=True,
    )

    weighed_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    station_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    station_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Weights (lb).
    gross_weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steer_axle_weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drive_axle_weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trailer_axle_weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_limit_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_over_legal_limit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    result: Mapped[str | None] = mapped_column(
        Enum(
            "pass",
            "bypass",
            "cited",
            "out_of_service",
            name="weigh_station_result",
        ),
        nullable=True,
    )
    citation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspector_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    doc_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        Enum("manual", "tms", name="weigh_station_report_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_weigh_station_reports_org_vehicle_weighed",
            "org_id",
            "adc_vehicle_id",
            "weighed_at_utc",
        ),
        Index(
            "ix_weigh_station_reports_org_external_id",
            "org_id",
            "external_id",
            unique=True,
        ),
        Index(
            "ix_weigh_station_reports_org_incident",
            "org_id",
            "incident_id",
        ),
    )


class LoadingDockReport(Base):
    """Loading-dock cargo + securement report.

    Photos are linked many-to-one via :attr:`Artifact.loading_dock_report_id`.
    The same FK pattern is reused by the future imaging-integration project
    for digitized weigh tickets and dispatch sheets — no further schema
    churn required.
    """

    __tablename__ = "loading_dock_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adc_trailer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    adc_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_instruction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dispatch_instructions.id", ondelete="SET NULL"),
        nullable=True,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="SET NULL"),
        nullable=True,
    )

    loaded_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    facility_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    facility_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cargo.
    commodity: Mapped[str | None] = mapped_column(Text, nullable=True)
    pieces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    net_weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seal_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Securement / load quality.
    securement_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_distribution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_overloaded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_improperly_loaded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Sign-off.
    loaded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    dock_supervisor: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        Enum("manual", "tms", name="loading_dock_report_source"),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_loading_dock_reports_org_trailer_loaded",
            "org_id",
            "adc_trailer_id",
            "loaded_at_utc",
        ),
        Index(
            "ix_loading_dock_reports_org_external_id",
            "org_id",
            "external_id",
            unique=True,
        ),
        Index(
            "ix_loading_dock_reports_org_incident",
            "org_id",
            "incident_id",
        ),
    )


class TmsConnection(Base):
    """Per-org configuration for an ODBC-based TMS data source."""

    __tablename__ = "tms_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    vendor_hint: Mapped[str] = mapped_column(
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
    odbc_secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_cron: Mapped[str] = mapped_column(
        Text, nullable=False, default="0 3 * * *", server_default="0 3 * * *"
    )
    last_synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "disabled", "error", name="tms_connection_status"),
        nullable=False,
        default="active",
        server_default="active",
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = ()


class TmsFieldMap(Base):
    """A single source-column → target-field mapping for a TMS connection."""

    __tablename__ = "tms_field_maps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tms_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tms_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity: Mapped[str] = mapped_column(
        Enum(
            "trailer",
            "maintenance_record",
            "dispatch_instruction",
            "weigh_station_report",
            "loading_dock_report",
            "driver_unit_history",
            name="tms_field_map_entity",
        ),
        nullable=False,
    )
    source_table: Mapped[str] = mapped_column(Text, nullable=False)
    source_column: Mapped[str] = mapped_column(Text, nullable=False)
    target_field: Mapped[str] = mapped_column(Text, nullable=False)
    transform: Mapped[str] = mapped_column(
        Text, nullable=False, default="none", server_default="none"
    )
    is_key: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_tms_field_maps_conn_entity",
            "tms_connection_id",
            "entity",
        ),
    )


# ── Insurance form templates + fillings (Phase 3) ──


class InsuranceFormTemplate(Base):
    """Operator-uploaded blank insurance form (org-scoped, not incident-scoped).

    The blank PDF/image lives in S3 referenced by ``s3_bucket`` / ``s3_key``.
    Once :attr:`status` is ``'finalized'`` the field map is locked; further
    edits create a new version.
    """

    __tablename__ = "insurance_form_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    carrier: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    status: Mapped[str] = mapped_column(
        Enum("draft", "finalized", "archived", name="insurance_form_template_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    s3_bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    finalized_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_insurance_form_templates_org_name_version",
            "org_id",
            "name",
            "version",
            unique=True,
        ),
    )


class InsuranceFormTemplateField(Base):
    """One mapped field on an insurance form template.

    ``source_path`` is a dot-notation path into the canonical
    ``CrashPacketRow`` (e.g. ``incident.adc_vehicle_id``,
    ``maintenance[0].vendor``). ``transform`` reuses the Phase 2
    enumeration (``none|date|upper|json_extract:<path>``).

    ``kind`` indicates the AcroForm/visual field type so the renderer can
    pick a sensible widget. ``page`` and ``bbox_json`` are populated when
    the operator (or AcroForm detection) has positional information; the
    MVP renderer only needs ``label`` + resolved value.
    """

    __tablename__ = "insurance_form_template_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "insurance_form_templates.id", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(
        Enum(
            "text",
            "date",
            "checkbox",
            "signature",
            name="insurance_form_field_kind",
        ),
        nullable=False,
        default="text",
        server_default="text",
    )
    bbox_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transform: Mapped[str] = mapped_column(
        Text, nullable=False, default="none", server_default="none"
    )
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_insurance_form_template_fields_template_name",
            "template_id",
            "name",
            unique=True,
        ),
    )


class InsuranceFormFilling(Base):
    """One materialized fill of an insurance form for an incident.

    Idempotent on ``(incident_id, template_id, payload_hash)`` — re-running
    the fill task with unchanged data does not produce a duplicate
    Artifact. Errors (missing required fields, render failures) are
    captured in ``status`` + ``error_message``.
    """

    __tablename__ = "insurance_form_fillings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("insurance_form_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "filled",
            "failed",
            name="insurance_form_filling_status",
        ),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    payload_hash: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    output_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )
    missing_required_fields: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    filled_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_insurance_form_fillings_incident_template_hash",
            "incident_id",
            "template_id",
            "payload_hash",
        ),
    )


# ── FMCSA MCMIS + driver unit history (slip-seating support) ──


class DriverUnitHistory(Base):
    """Slip-seating-aware history of tractor/trailer assignments per driver.

    Sourced primarily from TMS driver-history rows; falls back to a
    ``derived_from_assignment`` row built from ``DriverVehicleAssignment``
    when no TMS feed is mapped (always low-confidence).
    """

    __tablename__ = "driver_unit_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.driver_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    adc_driver_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_kind: Mapped[str] = mapped_column(
        Enum("tractor", "trailer", name="driver_unit_kind"), nullable=False
    )
    adc_vehicle_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    vin: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_plate: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ended_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(
        Enum(
            "tms",
            "eld",
            "manual",
            "derived_from_assignment",
            name="driver_unit_history_source",
        ),
        nullable=False,
        default="tms",
        server_default="tms",
    )
    source_record_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(
        Enum("high", "medium", "low", name="driver_unit_history_confidence"),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    confidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_driver_unit_history_org_driver_started",
            "org_id",
            "driver_id",
            "started_at_utc",
        ),
        Index("ix_driver_unit_history_org_vin", "org_id", "vin"),
        Index(
            "ix_driver_unit_history_org_plate_state",
            "org_id",
            "license_plate",
            "license_state",
        ),
        Index(
            "ix_driver_unit_history_org_external_id",
            "org_id",
            "external_id",
            unique=True,
        ),
    )


class FmcsaInspectionSnapshot(Base):
    """Per-org envelope for one FMCSA MCMIS pull (cached for ~6h)."""

    __tablename__ = "fmcsa_inspection_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usdot_number: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    window_start_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    window_end_utc: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        Enum("succeeded", "partial", "failed", name="fmcsa_snapshot_status"),
        nullable=False,
        default="succeeded",
        server_default="succeeded",
    )
    error_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    __table_args__ = (
        Index(
            "ix_fmcsa_inspection_snapshots_org_fetched",
            "org_id",
            "fetched_at_utc",
        ),
    )


class FmcsaInspection(Base):
    """A single normalized FMCSA inspection row.

    NOTE: deliberately omits any ``driver_*`` fields that the FMCSA
    dataset exposes — driver attribution is internal-only via
    :mod:`app.services.fmcsa_attribution`.
    """

    __tablename__ = "fmcsa_inspections"

    inspection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fmcsa_inspection_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_number: Mapped[str] = mapped_column(Text, nullable=False)
    inspection_date_utc: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    report_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    usdot_number: Mapped[str] = mapped_column(Text, nullable=False)
    vehicle_vin: Mapped[str | None] = mapped_column(Text, nullable=True)
    vehicle_license_plate: Mapped[str | None] = mapped_column(Text, nullable=True)
    vehicle_license_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_type: Mapped[str] = mapped_column(
        Enum("tractor", "trailer", "other", name="fmcsa_unit_type"),
        nullable=False,
        default="other",
        server_default="other",
    )
    inspection_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    oos_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    violation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    violations_json: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    raw_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_fmcsa_inspections_org_report_unique",
            "org_id",
            "report_number",
            unique=True,
        ),
        Index("ix_fmcsa_inspections_org_vin", "org_id", "vehicle_vin"),
        Index(
            "ix_fmcsa_inspections_org_plate_state",
            "org_id",
            "vehicle_license_plate",
            "vehicle_license_state",
        ),
        Index(
            "ix_fmcsa_inspections_org_date", "org_id", "inspection_date_utc"
        ),
    )


class IncidentDriverViolationHistory(Base):
    """Per-incident attribution of FMCSA inspections to a driver.

    Low-confidence rows are persisted (with ``excluded_reason``) but
    excluded from API responses and PDF (see
    :func:`app.db.repo.fmcsa_inspections.list_violation_history_for_incident`).
    """

    __tablename__ = "incident_driver_violation_history"

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fmcsa_inspections.inspection_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.driver_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    unit_history_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("driver_unit_history.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    match_basis: Mapped[str] = mapped_column(
        Enum("vin", "plate_state", name="fmcsa_match_basis"),
        nullable=False,
    )
    match_confidence: Mapped[str] = mapped_column(
        Enum("high", "medium", "low", name="fmcsa_match_confidence"),
        nullable=False,
    )
    included_in_brief: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    excluded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_incident_driver_violation_history_unique",
            "incident_id",
            "inspection_id",
            unique=True,
        ),
        Index(
            "ix_incident_driver_violation_history_incident_included",
            "incident_id",
            "included_in_brief",
        ),
    )
