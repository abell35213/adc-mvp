from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Event, Incident, Org
from app.domain.system_event_types import SystemEventType
from app.services.incident_workflow_service import initiate_driver_incident


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org(db_session):
    record = Org(name="Workflow Org")
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def _initiate(
    db_session, org: Org, driver_id: uuid.UUID, *, idempotency_key: str | None
):
    return initiate_driver_incident(
        db_session,
        org_id=org.id,
        driver_id=driver_id,
        adc_vehicle_id="veh-100",
        vehicle_strategy="last_assigned",
        device_location={"lat": 40.0, "lon": -74.0},
        device={"platform": "ios"},
        idempotency_key=idempotency_key,
    )


def _events(db_session, incident: Incident, event_type: SystemEventType) -> list[Event]:
    return (
        db_session.query(Event)
        .filter(
            Event.incident_id == incident.incident_id,
            Event.event_type == event_type.value,
        )
        .all()
    )


def test_initiate_driver_incident_writes_protocol_and_lockdown_exactly_once_for_retry(
    db_session,
    org,
):
    driver_id = uuid.uuid4()

    first = _initiate(db_session, org, driver_id, idempotency_key="retry-key")
    second = _initiate(db_session, org, driver_id, idempotency_key="retry-key")

    assert first.protocol_already_started is False
    assert second.protocol_already_started is True
    assert first.incident.incident_id == second.incident.incident_id
    assert db_session.query(Incident).count() == 1

    protocol_events = _events(
        db_session,
        first.incident,
        SystemEventType.INCIDENT_PROTOCOL_INITIATED,
    )
    lockdown_events = _events(
        db_session,
        first.incident,
        SystemEventType.EVIDENCE_LOCKDOWN_STARTED,
    )
    assert len(protocol_events) == 1
    assert len(lockdown_events) == 1
    assert protocol_events[0].payload["idempotency_key"] == "retry-key"
    assert protocol_events[0].payload["idempotency_key_hash"]


def test_initiate_driver_incident_does_not_duplicate_with_new_key_after_protocol_started(
    db_session,
    org,
):
    driver_id = uuid.uuid4()

    first = _initiate(db_session, org, driver_id, idempotency_key="original-key")
    second = _initiate(db_session, org, driver_id, idempotency_key="new-key")

    assert second.protocol_already_started is True
    assert first.incident.incident_id == second.incident.incident_id
    assert (
        len(
            _events(
                db_session, first.incident, SystemEventType.INCIDENT_PROTOCOL_INITIATED
            )
        )
        == 1
    )
    assert (
        len(
            _events(
                db_session, first.incident, SystemEventType.EVIDENCE_LOCKDOWN_STARTED
            )
        )
        == 1
    )


def test_initiate_driver_incident_uses_existing_active_vehicle_incident_once(
    db_session, org
):
    driver_id = uuid.uuid4()
    existing = Incident(
        org_id=org.id,
        adc_vehicle_id="veh-100",
        adc_driver_id=None,
        status="evidence_capturing",
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    result = _initiate(db_session, org, driver_id, idempotency_key=None)

    assert result.protocol_already_started is False
    assert result.incident.incident_id == existing.incident_id
    assert db_session.query(Incident).count() == 1
    assert (
        len(_events(db_session, existing, SystemEventType.INCIDENT_PROTOCOL_INITIATED))
        == 1
    )
