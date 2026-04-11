"""Tests for Twilio Verify wrapper via integration provider."""

from unittest.mock import patch

from app.integrations.providers.twilio import TwilioMessagingProvider
from app.services import twilio_verify


def test_start_verification_delegates_to_provider():
    with patch.object(TwilioMessagingProvider, "start_verification", return_value="VE123") as start:
        sid = twilio_verify.start_verification("+15551234567")

    assert sid == "VE123"
    start.assert_called_once_with("+15551234567")


def test_check_verification_returns_true_for_approved():
    with patch.object(TwilioMessagingProvider, "check_verification", return_value=True) as check:
        assert twilio_verify.check_verification("+15551234567", "123456") is True

    check.assert_called_once_with("+15551234567", "123456")
