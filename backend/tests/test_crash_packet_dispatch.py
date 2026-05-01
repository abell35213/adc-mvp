"""Tests for crash-packet dispatch task + SLA watchdog (plan test #3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    CrashPacketDelivery,
    Driver,
    Event,
    Incident,
    Org,
    OrgNotificationRecipient,
    OrgVehicleRegistry,
)
from app.domain.system_event_types import SystemEventType
from app.integrations.errors import IntegrationError, NormalizedIntegrationError
from app.tasks.crash_packet_tasks import (
    crash_packet_sla_watchdog,
    dispatch_crash_packet,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org(db_session):
    org = Org(name="Acme")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def incident(db_session, org):
    driver = Driver(
        org_id=org.id, phone_e164="+15551234567", display_name="Pat Driver"
    )
    db_session.add(driver)
    vehicle = OrgVehicleRegistry(org_id=org.id, unit_number="T-100")
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(driver)
    db_session.refresh(vehicle)

    inc = Incident(
        status="accident_occurred",
        adc_vehicle_id="T-100",
        adc_driver_id=str(driver.driver_id),
        severity="serious",
        org_id=org.id,
    )
    db_session.add(inc)
    db_session.commit()
    db_session.refresh(inc)
    return inc


@pytest.fixture()
def recipients(db_session, org):
    rs = [
        OrgNotificationRecipient(
            org_id=org.id,
            email=f"safety{i}@example.com",
            full_name=f"Safety {i}",
            channels=["email"],
            active=True,
        )
        for i in range(2)
    ]
    db_session.add_all(rs)
    db_session.commit()
    return rs


def _events_of_type(db_session, incident_id, event_type):
    return [
        e
        for e in db_session.query(Event)
        .filter(Event.incident_id == incident_id, Event.event_type == event_type)
        .all()
    ]


class TestDispatchCrashPacket:
    def test_happy_path_sends_to_every_active_recipient(
        self, db_session, incident, recipients
    ):
        sent_calls: list[dict] = []

        def fake_send(*, to, subject, html_body, text_body=None, attachments=None):
            sent_calls.append({"to": to, "subject": subject})
            return f"msg-{len(sent_calls)}"

        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            import app.services.email_provider as ep_mod

            original = ep_mod.send_email
            ep_mod.send_email = fake_send  # type: ignore[assignment]
            try:
                result = dispatch_crash_packet(str(incident.incident_id))
            finally:
                ep_mod.send_email = original  # type: ignore[assignment]

        assert result["status"] == "sent"
        assert result["sent_count"] == 2
        assert result["failed_count"] == 0
        assert len(sent_calls) == 2
        assert sorted(c["to"] for c in sent_calls) == [
            "safety0@example.com",
            "safety1@example.com",
        ]
        # Audit trail
        assert _events_of_type(
            db_session, incident.incident_id, SystemEventType.CRASH_PACKET_DISPATCHED.value
        )
        assert _events_of_type(
            db_session, incident.incident_id, SystemEventType.CRASH_PACKET_SENT.value
        )

    def test_idempotent_when_already_sent(self, db_session, incident, recipients):
        # Pre-existing 'sent' delivery row → second call should short-circuit.
        delivery = CrashPacketDelivery(
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            status="sent",
            target_sla_seconds=900,
            idempotency_key=f"crash_packet:{incident.incident_id}",
        )
        db_session.add(delivery)
        db_session.commit()

        called = {"n": 0}

        def fake_send(**_kw):
            called["n"] += 1
            return "should-not-be-called"

        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            import app.services.email_provider as ep_mod

            original = ep_mod.send_email
            ep_mod.send_email = fake_send  # type: ignore[assignment]
            try:
                result = dispatch_crash_packet(str(incident.incident_id))
            finally:
                ep_mod.send_email = original  # type: ignore[assignment]

        assert result["status"] == "sent"
        assert called["n"] == 0

    def test_partial_bounce_records_failed_recipients(
        self, db_session, incident, recipients
    ):
        seq = iter(["msg-1"])

        def fake_send(*, to, **_kw):
            if to == "safety1@example.com":
                raise IntegrationError(
                    NormalizedIntegrationError(
                        code="EMAIL_INVALID_DESTINATION",
                        category="email",
                        provider_key="ses",
                        retryable=False,
                        user_facing_message="Address rejected.",
                        operator_message="bounce",
                    )
                )
            return next(seq)

        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            import app.services.email_provider as ep_mod

            original = ep_mod.send_email
            ep_mod.send_email = fake_send  # type: ignore[assignment]
            try:
                result = dispatch_crash_packet(str(incident.incident_id))
            finally:
                ep_mod.send_email = original  # type: ignore[assignment]

        assert result["status"] == "partial"
        assert result["sent_count"] == 1
        assert result["failed_count"] == 1
        delivery = (
            db_session.query(CrashPacketDelivery)
            .filter(CrashPacketDelivery.incident_id == incident.incident_id)
            .one()
        )
        assert delivery.status == "partial"
        assert delivery.failed_to[0]["email"] == "safety1@example.com"
        assert delivery.failed_to[0]["error_code"] == "EMAIL_INVALID_DESTINATION"

    def test_no_recipients_marks_failed(self, db_session, incident):
        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            result = dispatch_crash_packet(str(incident.incident_id))
        assert result["status"] == "failed"
        assert result["reason"] == "no_active_recipients"
        assert _events_of_type(
            db_session,
            incident.incident_id,
            SystemEventType.CRASH_PACKET_FAILED.value,
        )


class TestSlaWatchdog:
    def test_marks_overdue_deliveries(self, db_session, incident):
        # Dispatched 16 minutes ago, SLA 15 → overdue.
        long_ago = datetime.now(timezone.utc) - timedelta(minutes=16)
        delivery = CrashPacketDelivery(
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            status="dispatched",
            target_sla_seconds=900,
            idempotency_key=f"crash_packet:{incident.incident_id}",
            dispatched_at_utc=long_ago,
        )
        db_session.add(delivery)
        db_session.commit()

        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            result = crash_packet_sla_watchdog()

        assert result["overdue_count"] == 1
        reloaded = (
            db_session.query(CrashPacketDelivery)
            .filter(CrashPacketDelivery.id == delivery.id)
            .one()
        )
        assert reloaded.status == "overdue"
        assert _events_of_type(
            db_session,
            incident.incident_id,
            SystemEventType.CRASH_PACKET_OVERDUE.value,
        )

    def test_does_not_flip_within_sla(self, db_session, incident):
        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        delivery = CrashPacketDelivery(
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            status="dispatched",
            target_sla_seconds=900,
            idempotency_key=f"crash_packet:{incident.incident_id}",
            dispatched_at_utc=recent,
        )
        db_session.add(delivery)
        db_session.commit()

        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            result = crash_packet_sla_watchdog()

        assert result["overdue_count"] == 0
        reloaded = (
            db_session.query(CrashPacketDelivery)
            .filter(CrashPacketDelivery.id == delivery.id)
            .one()
        )
        assert reloaded.status == "dispatched"

    def test_does_not_touch_already_sent(self, db_session, incident):
        long_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
        delivery = CrashPacketDelivery(
            incident_id=incident.incident_id,
            org_id=incident.org_id,
            status="sent",
            target_sla_seconds=900,
            idempotency_key=f"crash_packet:{incident.incident_id}",
            dispatched_at_utc=long_ago,
        )
        db_session.add(delivery)
        db_session.commit()

        with patch("app.tasks.crash_packet_tasks._get_db", return_value=db_session):
            result = crash_packet_sla_watchdog()

        assert result["overdue_count"] == 0
        reloaded = (
            db_session.query(CrashPacketDelivery)
            .filter(CrashPacketDelivery.id == delivery.id)
            .one()
        )
        assert reloaded.status == "sent"
