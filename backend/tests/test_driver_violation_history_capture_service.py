"""Tests for the FMCSA driver-violation-history capture service.

The service is responsible for:

* Creating one ``EvidenceRequest`` (provider=``fmcsa``,
  domain=``inspections``) and one ``IntegrationOperation``.
* Enqueueing the Celery task ``capture_driver_violation_history`` with
  the right arguments.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, EvidenceRequest, Incident, IntegrationOperation, Org


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionMaker = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org_and_incident(db_session):
    org = Org(name="Acme Trucking", sms_enabled=False, voice_enabled=False)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    incident = Incident(
        org_id=org.id,
        status="open",
        adc_driver_id=str(uuid.uuid4()),
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return org, incident


def test_queue_creates_request_operation_and_enqueues_task(
    db_session, org_and_incident, monkeypatch
):
    org, incident = org_and_incident

    delays: list[dict] = []

    class _FakeTask:
        def delay(self, **kwargs):
            delays.append(kwargs)

    fake_task = _FakeTask()
    monkeypatch.setattr(
        "app.tasks.evidence_tasks.capture_driver_violation_history",
        fake_task,
    )

    from app.services.driver_violation_history_capture_service import (
        queue_driver_violation_history_capture,
    )

    op_id = queue_driver_violation_history_capture(
        db_session,
        org_id=org.id,
        incident_id=incident.incident_id,
        adc_driver_id=incident.adc_driver_id,
        usdot_number="12345678",
        api_correlation_id="test-corr",
    )

    assert op_id is not None

    # IntegrationOperation row was created with the correct domain/provider.
    op = (
        db_session.query(IntegrationOperation)
        .filter(IntegrationOperation.operation_id == op_id)
        .first()
    )
    assert op is not None
    assert op.domain == "inspections"
    assert op.provider == "fmcsa"
    assert op.incident_id == incident.incident_id
    assert op.payload_json["usdot_number"] == "12345678"

    # EvidenceRequest row exists and points at the operation.
    er = (
        db_session.query(EvidenceRequest)
        .filter(EvidenceRequest.operation_id == op_id)
        .first()
    )
    assert er is not None
    assert er.provider == "fmcsa"
    assert er.domain == "inspections"
    assert er.external_reference == "12345678"

    # Celery delay was called with the right keyword args.
    assert len(delays) == 1
    payload = delays[0]
    assert payload["usdot_number"] == "12345678"
    assert payload["org_id"] == str(org.id)
    assert payload["incident_id"] == str(incident.incident_id)
    assert payload["adc_driver_id"] == incident.adc_driver_id
    assert uuid.UUID(payload["operation_id"]) == op_id


def test_repo_get_meta_for_incident_with_no_attributions_returns_zeros(db_session):
    from app.db.repo.fmcsa_inspections import get_meta_for_incident

    meta = get_meta_for_incident(db_session, uuid.uuid4())
    assert meta == {
        "total_inspections_pulled": 0,
        "included_count": 0,
        "low_confidence_excluded_count": 0,
        "last_refreshed_at_utc": None,
        "snapshot_status": None,
    }
