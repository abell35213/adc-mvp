"""Tests for Twilio webhook routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_twilio import VOICE_MESSAGE, _build_twilio_signature
from app.core.config import settings
from app.db.models import Base, MessageOperation, Org
from app.db.repo.message_operations import create_message_operation
from app.db.session import get_db
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
