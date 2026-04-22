"""Tests for Twilio webhook routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_twilio import VOICE_MESSAGE, _build_twilio_signature
from app.core.config import settings
from app.core.metrics import MetricNames
from app.db.models import Base, MessageOperation, Org, ProviderWebhookEvent
from app.db.repo.message_operations import create_message_operation
from app.db.session import get_db
from app.integrations.webhooks import handlers
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_twilio_voice_rejects_missing_signature(monkeypatch, client):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")

    response = client.post("/twilio/voice", data={"CallSid": "CA123"})

    assert response.status_code == 403


def test_twilio_voice_persists_invalid_signature_event(monkeypatch, client, db_session):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")

    response = client.post("/twilio/voice", data={"CallSid": "CA123"})

    assert response.status_code == 403
    webhook_event = db_session.query(ProviderWebhookEvent).first()
    assert webhook_event is not None
    assert webhook_event.signature_valid is False
    assert webhook_event.status == "failed"
    assert webhook_event.processing_outcome == "invalid_signature"


def test_twilio_voice_accepts_valid_signature(monkeypatch, client):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    params = {"CallSid": "CA123", "From": "+15551234567"}
    url = f"{client.base_url}/twilio/voice"
    signature = _build_twilio_signature("secret", url, params)

    response = client.post(
        "/twilio/voice",
        data=params,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert VOICE_MESSAGE in response.text


def test_twilio_status_callback_reconciles_message_operation(monkeypatch, client, db_session):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()

    create_message_operation(
        db_session,
        org_id=org.id,
        provider="twilio",
        domain="messaging",
        purpose="safety_manager_sms_notification",
        to_e164="+15551234567",
        status="sent",
        provider_message_id="SM123",
    )

    params = {"MessageSid": "SM123", "MessageStatus": "delivered"}
    url = f"{client.base_url}/twilio/status"
    signature = _build_twilio_signature("secret", url, params)

    response = client.post(
        "/twilio/status",
        data=params,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    op = db_session.query(MessageOperation).filter(MessageOperation.provider_message_id == "SM123").first()
    assert op is not None
    assert op.status == "delivered"

    events = (
        db_session.query(ProviderWebhookEvent)
        .filter(ProviderWebhookEvent.event_type == "status_callback")
        .all()
    )
    assert len(events) == 1
    assert events[0].signature_valid is True
    assert events[0].processing_outcome == "message_operation_updated"


def test_twilio_status_callback_idempotency(monkeypatch, client, db_session):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()

    create_message_operation(
        db_session,
        org_id=org.id,
        provider="twilio",
        domain="messaging",
        purpose="safety_manager_sms_notification",
        to_e164="+15551234567",
        status="sent",
        provider_message_id="SM123",
    )

    params = {"MessageSid": "SM123", "MessageStatus": "delivered"}
    url = f"{client.base_url}/twilio/status"
    signature = _build_twilio_signature("secret", url, params)
    headers = {"X-Twilio-Signature": signature}

    response_1 = client.post("/twilio/status", data=params, headers=headers)
    response_2 = client.post("/twilio/status", data=params, headers=headers)

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_2.json()["status"] == "duplicate"

    events = (
        db_session.query(ProviderWebhookEvent)
        .filter(ProviderWebhookEvent.event_type == "status_callback")
        .order_by(ProviderWebhookEvent.received_at_utc.asc())
        .all()
    )
    assert len(events) == 2
    assert events[0].status == "processed"
    assert events[1].status == "ignored"
    assert events[1].processing_outcome == "duplicate"


def test_twilio_status_callback_otp_metrics_only_for_otp_operations(
    monkeypatch, client, db_session
):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    org = Org(name="Test Org")
    db_session.add(org)
    db_session.commit()

    create_message_operation(
        db_session,
        org_id=org.id,
        provider="twilio",
        domain="messaging",
        purpose="safety_manager_sms_notification",
        to_e164="+15551234567",
        status="sent",
        provider_message_id="SM_NON_OTP",
    )
    create_message_operation(
        db_session,
        org_id=org.id,
        provider="twilio",
        domain="auth",
        purpose="otp_request",
        to_e164="+15557654321",
        status="sent",
        provider_message_id="SM_OTP",
    )

    emitted_metrics: list[str] = []

    def _capture(metric_name: str) -> None:
        emitted_metrics.append(metric_name)

    monkeypatch.setattr(handlers, "increment", _capture)

    non_otp_params = {"MessageSid": "SM_NON_OTP", "MessageStatus": "failed"}
    non_otp_sig = _build_twilio_signature(
        "secret", f"{client.base_url}/twilio/status", non_otp_params
    )
    otp_params = {"MessageSid": "SM_OTP", "MessageStatus": "delivered"}
    otp_sig = _build_twilio_signature(
        "secret", f"{client.base_url}/twilio/status", otp_params
    )

    non_otp_response = client.post(
        "/twilio/status",
        data=non_otp_params,
        headers={"X-Twilio-Signature": non_otp_sig},
    )
    otp_response = client.post(
        "/twilio/status",
        data=otp_params,
        headers={"X-Twilio-Signature": otp_sig},
    )

    assert non_otp_response.status_code == 200
    assert otp_response.status_code == 200
    assert MetricNames.OTP_DELIVERY_FAILURE not in emitted_metrics
    assert emitted_metrics.count(MetricNames.OTP_DELIVERY_SUCCESS) == 1
