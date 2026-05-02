"""Tests for the SES email provider adapter (plan test #4).

Uses a hand-rolled boto3 stub rather than ``moto`` so we avoid pulling in a
new test-only dependency for a small adapter surface.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.integrations.errors import IntegrationError
from app.integrations.providers.ses import (
    NoopEmailProvider,
    SESEmailProvider,
    build_default_email_provider,
)


class _FakeSESClient:
    """Minimal stand-in for ``boto3.client('sesv2')``."""

    def __init__(self, behavior: str = "ok"):
        self.behavior = behavior
        self.calls: list[dict] = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.behavior == "ok":
            return {"MessageId": "ses-msg-123"}
        if self.behavior == "throttle":
            raise _ClientError("Throttling", "Maximum sending rate exceeded")
        if self.behavior == "rejected":
            raise _ClientError("MessageRejected", "Bad address")
        if self.behavior == "auth":
            raise _ClientError("AccessDenied", "denied")
        raise RuntimeError("boom")


class _ClientError(Exception):
    """Lookalike for botocore ClientError carrying the same response shape."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}}


@pytest.fixture()
def ses_settings(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.providers.ses.settings.EMAIL_FROM",
        "alerts@adc.example",
    )
    monkeypatch.setattr(
        "app.integrations.providers.ses.settings.SES_REGION", "us-east-1"
    )
    monkeypatch.setattr(
        "app.integrations.providers.ses.settings.EMAIL_REPLY_TO",
        "noreply@adc.example",
    )
    monkeypatch.setattr(
        "app.integrations.providers.ses.settings.EMAIL_CONFIGURATION_SET",
        "adc-bounces",
    )


class TestSESEmailProvider:
    def test_send_email_returns_message_id_on_success(self, ses_settings):
        provider = SESEmailProvider()
        provider._client = _FakeSESClient("ok")

        msg_id = provider.send_email(
            to="dest@example.com",
            subject="Crash brief",
            html_body="<p>hi</p>",
            text_body="hi",
        )

        assert msg_id == "ses-msg-123"
        call = provider._client.calls[0]
        assert call["FromEmailAddress"] == "alerts@adc.example"
        assert call["Destination"] == {"ToAddresses": ["dest@example.com"]}
        body = call["Content"]["Simple"]["Body"]
        assert body["Html"]["Data"] == "<p>hi</p>"
        assert body["Text"]["Data"] == "hi"
        assert call["ReplyToAddresses"] == ["noreply@adc.example"]
        assert call["ConfigurationSetName"] == "adc-bounces"

    def test_throttling_raises_retryable_email_rate_limited(self, ses_settings):
        provider = SESEmailProvider()
        provider._client = _FakeSESClient("throttle")

        with pytest.raises(IntegrationError) as ei:
            provider.send_email(
                to="dest@example.com", subject="s", html_body="<p>h</p>"
            )

        assert ei.value.normalized_error.code == "EMAIL_RATE_LIMITED"
        assert ei.value.normalized_error.retryable is True

    def test_rejected_address_maps_to_invalid_destination(self, ses_settings):
        provider = SESEmailProvider()
        provider._client = _FakeSESClient("rejected")
        with pytest.raises(IntegrationError) as ei:
            provider.send_email(to="x@y", subject="s", html_body="<p>h</p>")
        assert ei.value.normalized_error.code == "EMAIL_INVALID_DESTINATION"
        assert ei.value.normalized_error.retryable is False

    def test_access_denied_maps_to_auth_failed(self, ses_settings):
        provider = SESEmailProvider()
        provider._client = _FakeSESClient("auth")
        with pytest.raises(IntegrationError) as ei:
            provider.send_email(to="x@y", subject="s", html_body="<p>h</p>")
        assert ei.value.normalized_error.code == "EMAIL_AUTH_FAILED"

    def test_unrecognized_failure_maps_to_provider_error(self, ses_settings):
        provider = SESEmailProvider()
        provider._client = _FakeSESClient("other")
        with pytest.raises(IntegrationError) as ei:
            provider.send_email(to="x@y", subject="s", html_body="<p>h</p>")
        assert ei.value.normalized_error.code == "EMAIL_PROVIDER_ERROR"

    def test_missing_email_from_raises_not_configured(self, monkeypatch):
        monkeypatch.setattr(
            "app.integrations.providers.ses.settings.EMAIL_FROM", ""
        )
        provider = SESEmailProvider()
        with pytest.raises(IntegrationError) as ei:
            provider.send_email(to="x@y", subject="s", html_body="<p>h</p>")
        assert ei.value.normalized_error.code == "EMAIL_NOT_CONFIGURED"


class TestNoopEmailProvider:
    def test_records_sends_and_returns_synthetic_id(self):
        provider = NoopEmailProvider()
        msg_id = provider.send_email(
            to="x@y", subject="s", html_body="<p>h</p>"
        )
        assert msg_id.startswith("noop-1-")
        assert provider.sent[0]["to"] == "x@y"


class TestBuildDefaultEmailProvider:
    def test_returns_ses_when_provider_setting_is_ses(self, monkeypatch):
        monkeypatch.setattr(
            "app.integrations.providers.ses.settings.EMAIL_PROVIDER", "ses"
        )
        provider = build_default_email_provider()
        assert isinstance(provider, SESEmailProvider)

    def test_returns_noop_otherwise(self, monkeypatch):
        monkeypatch.setattr(
            "app.integrations.providers.ses.settings.EMAIL_PROVIDER", "noop"
        )
        provider = build_default_email_provider()
        assert isinstance(provider, NoopEmailProvider)


class TestEmailProviderService:
    def test_send_email_helper_delegates_to_provider(self):
        from app.services.email_provider import send_email

        with patch(
            "app.services.email_provider.get_email_provider"
        ) as mock_get:
            mock_provider = NoopEmailProvider()
            mock_get.return_value = mock_provider
            msg_id = send_email(
                to="x@y", subject="s", html_body="<p>h</p>"
            )
        assert msg_id.startswith("noop-")
        assert mock_provider.sent[0]["to"] == "x@y"
