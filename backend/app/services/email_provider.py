"""Email send helpers backed by integration providers (mirrors twilio_notify)."""

from __future__ import annotations

from typing import Any

from app.integrations.errors import IntegrationError, as_normalized_error
from app.integrations.service import get_email_provider


def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    """Send a single email via the registered email provider.

    Returns the provider message id, or raises ``IntegrationError`` with a
    normalized payload on failure.
    """
    try:
        return get_email_provider().send_email(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
        )
    except IntegrationError:
        raise
    except Exception as exc:
        raise IntegrationError(
            as_normalized_error(exc, provider_hint="ses", category="email")
        ) from exc
