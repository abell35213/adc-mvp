"""Tests for OTP request schemas."""

import pytest
from pydantic import ValidationError

from app.api.schemas import RequestOtpRequest


def test_request_otp_request_accepts_phone_e164():
    payload = RequestOtpRequest(phone_e164="+15551234567")
    assert payload.phone_e164 == "+15551234567"


@pytest.mark.parametrize(
    "phone_e164",
    [
        "15551234567",
        "+0123456789",
        "+1-555-123-4567",
    ],
)
def test_request_otp_request_rejects_invalid_phone_e164(phone_e164):
    with pytest.raises(ValidationError):
        RequestOtpRequest(phone_e164=phone_e164)
