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

Base = declarative_base()


# ── Auth / multi-tenant models ─────────────────────────────────────


class Org(Base):
    """Organization (tenant)."""

    __tablename__ = "orgs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    require_driver_ack = Column(Boolean, nullable=False, default=False)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    voice_enabled = Column(Boolean, nullable=False, default=False)
    safety_manager_phone = Column(Text, nullable=True)
    instruction_source = Column(Text, nullable=False, default="default")


class User(Base):
    """Application user with hashed password and role."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default="safety_manager")
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_active = Column(Boolean, nullable=False, default=True)


class UserOrg(Base):
    """Many-to-many link between users and organizations."""

    __tablename__ = "user_orgs"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id"),
        primary_key=True,
    )


# ── Core domain models ─────────────────────────────────────────────


class Event(Base):
    """Append-only event log — source of truth. No updates, no deletes."""

    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id"),
        nullable=True,
        index=True,
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


class Incident(Base):
    """Summary pointer for an incident."""

    __tablename__ = "incidents"

    incident_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True
    )
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    status = Column(
        Enum("open", "evidence_capturing", "closed", name="incident_status"),
        nullable=False,
        default="open",
    )
    adc_vehicle_id = Column(Text, nullable=True)
    samsara_vehicle_id = Column(Text, nullable=True)
    adc_driver_id = Column(Text, nullable=True)
    severity = Column(Text, nullable=True)


class Artifact(Base):
    """Metadata lookup for evidence artifacts."""

    __tablename__ = "artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id"),
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
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum("requested", "processing", "ready", "failed", name="export_status"),
        nullable=False,
        default="requested",
    )
    s3_bucket = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_exports_org_incident", "org_id", "incident_id"),)


# ── Driver protocol models ────────────────────────────────────────────


class Driver(Base):
    """Driver profile for communications and assignments."""

    __tablename__ = "drivers"

    driver_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
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
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )
    driver_id = Column(
        UUID(as_uuid=True), ForeignKey("drivers.driver_id"), nullable=False, index=True
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


class VehicleQrToken(Base):
    """Vehicle QR tokens for driver app onboarding."""

    __tablename__ = "vehicle_qr_tokens"

    qr_token = Column(Text, primary_key=True)
    org_id = Column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
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
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
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
        ForeignKey("driver_instruction_sets.instruction_set_id"),
        nullable=False,
        index=True,
    )
    step_order = Column("order", Integer, nullable=False, quote=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
