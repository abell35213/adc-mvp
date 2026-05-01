"""Email provider adapters (SES + a no-op for local/test)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.integrations.errors import (
    IntegrationError,
    NormalizedIntegrationError,
    map_ses_error,
)

logger = logging.getLogger(__name__)


class NoopEmailProvider:
    """Email provider that records sends in-memory and returns synthetic ids.

    Used when ``EMAIL_PROVIDER`` is unset/``noop`` (local dev, tests). Behaves
    like a successful sender so the rest of the pipeline can be exercised
    without real AWS credentials.
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        record = {
            "to": to,
            "subject": subject,
            "html_body": html_body,
            "text_body": text_body,
            "attachments": list(attachments or []),
        }
        self.sent.append(record)
        synthetic_id = f"noop-{len(self.sent)}-{abs(hash(to + subject)) % 10_000_000}"
        logger.info("NoopEmailProvider.send_email recipient=%s id=%s", to, synthetic_id)
        return synthetic_id


class SESEmailProvider:
    """AWS SES adapter using boto3 (already a project dependency)."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not settings.EMAIL_FROM:
            raise IntegrationError(
                NormalizedIntegrationError(
                    code="EMAIL_NOT_CONFIGURED",
                    category="email",
                    provider_key="ses",
                    retryable=False,
                    user_facing_message="Email sender is not configured.",
                    operator_message="EMAIL_FROM is empty; configure SES sender address.",
                )
            )
        import boto3  # local import to keep startup light

        self._client = boto3.client("sesv2", region_name=settings.SES_REGION)
        return self._client

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        client = self._get_client()
        body: dict[str, Any] = {"Html": {"Data": html_body, "Charset": "UTF-8"}}
        if text_body:
            body["Text"] = {"Data": text_body, "Charset": "UTF-8"}
        request_kwargs: dict[str, Any] = {
            "FromEmailAddress": settings.EMAIL_FROM,
            "Destination": {"ToAddresses": [to]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": body,
                }
            },
        }
        if settings.EMAIL_REPLY_TO:
            request_kwargs["ReplyToAddresses"] = [settings.EMAIL_REPLY_TO]
        if settings.EMAIL_CONFIGURATION_SET:
            request_kwargs["ConfigurationSetName"] = settings.EMAIL_CONFIGURATION_SET

        # NOTE: attachments are intentionally not supported by the simple
        # SES path. The crash-packet PDF is referenced via a presigned link in
        # the HTML body to avoid SES's 10 MB raw-message ceiling and to keep
        # this Phase-1 surface small.
        try:
            response = client.send_email(**request_kwargs)
        except Exception as exc:
            raise IntegrationError(map_ses_error(exc)) from exc
        return response.get("MessageId", "")


def build_default_email_provider():
    """Factory honoring the EMAIL_PROVIDER setting."""
    if settings.EMAIL_PROVIDER == "ses":
        return SESEmailProvider()
    return NoopEmailProvider()
