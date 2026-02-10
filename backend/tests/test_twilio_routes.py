"""Tests for Twilio webhook routes."""

from fastapi.testclient import TestClient

from app.api.routes_twilio import VOICE_MESSAGE, _build_twilio_signature
from app.core.config import settings
from app.main import app


def test_twilio_voice_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    client = TestClient(app)

    response = client.post("/twilio/voice", data={"CallSid": "CA123"})

    assert response.status_code == 403


def test_twilio_voice_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret")
    client = TestClient(app)
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
