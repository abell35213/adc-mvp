from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.models import AuditEventCreate
from app.audit.service import append_event, get_events, set_retention
from app.db.models import Base, Org


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)
    session = test_session()
    try:
        yield session
    finally:
        session.close()


def test_append_and_query_audit_events(db_session) -> None:
    org = Org(name="Audit Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    now = datetime.now(timezone.utc)
    append_event(
        db_session,
        AuditEventCreate(
            org_id=org.id,
            actor_type="user",
            actor_id="user-1",
            action="export.download",
            event_type="export_downloaded",
            outcome="success",
            metadata={"ip": "127.0.0.1"},
            occurred_at_utc=now,
        ),
    )

    events = get_events(
        db_session,
        org_id=org.id,
        actor_id="user-1",
        event_type="export_downloaded",
        occurred_after_utc=now - timedelta(minutes=1),
        occurred_before_utc=now + timedelta(minutes=1),
    )

    assert len(events) == 1
    assert events[0].action == "export.download"
    assert events[0].outcome == "success"


def test_retention_fields_can_be_updated(db_session) -> None:
    org = Org(name="Retention Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    event = append_event(
        db_session,
        AuditEventCreate(
            org_id=org.id,
            actor_type="system",
            actor_id="scheduler",
            action="retention.mark",
            event_type="retention_marked",
        ),
    )

    retention_until = datetime.now(timezone.utc) + timedelta(days=365)
    updated = set_retention(
        db_session,
        audit_event_id=event.id,
        retention_expires_at_utc=retention_until,
    )

    assert updated is not None
    assert updated.retention_expires_at_utc == retention_until.replace(tzinfo=None)
