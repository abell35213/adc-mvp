"""SQLAlchemy database models."""

import uuid

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import declarative_base
from sqlalchemy import BigInteger

Base = declarative_base()


# ── Auth / multi-tenant models ─────────────────────────────────────


class Org(Base):
    """Organization (tenant)."""

    __tablename__ = "orgs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)


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
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True)
    incident_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(Text, nullable=False, index=True)
    occurred_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    actor_type = Column(Text, nullable=False)
    actor_id = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)


class Incident(Base):
    """Summary pointer for an incident."""

    __tablename__ = "incidents"

    incident_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    status = Column(Text, nullable=False, default="open")
    adc_vehicle_id = Column(Text, nullable=True)
    samsara_vehicle_id = Column(Text, nullable=True)
    adc_driver_id = Column(Text, nullable=True)
    severity = Column(Text, nullable=True)


class Artifact(Base):
    """Metadata lookup for evidence artifacts."""

    __tablename__ = "artifacts"

    artifact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True)
    incident_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    artifact_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    capture_window_start_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    capture_window_end_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    s3_bucket = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)
    sha256 = Column(Text, nullable=True)
    byte_size = Column(BigInteger, nullable=True)
    unavailable_reason_code = Column(Text, nullable=True)
    unavailable_reason_detail = Column(Text, nullable=True)


class Export(Base):
    """Export request tracking."""

    __tablename__ = "exports"

    export_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=True, index=True)
    incident_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(Text, nullable=False, default="requested")
    s3_bucket = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)
    created_at_utc = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
