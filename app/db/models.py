"""SQLAlchemy database models."""

from sqlalchemy import Column, Integer, String, DateTime, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, nullable=False, index=True)
    artifact_type = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Export(Base):
    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, nullable=False, index=True)
    format = Column(String, nullable=False)
    storage_path = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
