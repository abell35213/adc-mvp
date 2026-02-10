"""Tests for OTP request schemas."""

from app.api.schemas import RequestOtpRequest


def test_request_otp_request_accepts_phone_e164():
    payload = RequestOtpRequest(phone_e164="+15551234567")
    assert payload.phone_e164 == "+15551234567"
