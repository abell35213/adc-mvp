"""Tests for Twilio Verify HTTP client wrapper."""

from unittest.mock import Mock, patch

from app.services import twilio_verify


def _mock_response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_start_verification_uses_verify_endpoint(monkeypatch):
    monkeypatch.setattr(twilio_verify.settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(twilio_verify.settings, "TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setattr(
        twilio_verify.settings,
        "TWILIO_VERIFY_SERVICE_SID",
        "VA123",
    )
    with patch("app.services.twilio_verify.httpx.post") as post:
        post.return_value = _mock_response({"sid": "VE123"})
        sid = twilio_verify.start_verification("+15551234567")

    assert sid == "VE123"
    assert "/Services/VA123/Verifications" in post.call_args.args[0]


def test_check_verification_returns_true_for_approved(monkeypatch):
    monkeypatch.setattr(twilio_verify.settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(twilio_verify.settings, "TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setattr(
        twilio_verify.settings,
        "TWILIO_VERIFY_SERVICE_SID",
        "VA123",
    )
    with patch("app.services.twilio_verify.httpx.post") as post:
        post.return_value = _mock_response({"status": "approved"})
        assert twilio_verify.check_verification("+15551234567", "123456") is True
