"""Webhook signature helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import parse_qs


def flatten_form_params(raw_params: dict[str, list[str]]) -> dict[str, str]:
    """Flatten repeated form params into strings for signature computation."""
    params: dict[str, str] = {}
    for key, values in raw_params.items():
        if not values:
            params[key] = ""
        elif len(values) == 1:
            params[key] = values[0]
        else:
            params[key] = ",".join(values)
    return params


def parse_form_encoded_body(raw_body: bytes) -> dict[str, str]:
    return flatten_form_params(
        parse_qs(raw_body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    )


def build_twilio_signature(auth_token: str, request_url: str, params: dict[str, str]) -> str:
    message = request_url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode(), message.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def validate_twilio_signature(
    *,
    auth_token: str | None,
    request_url: str,
    params: dict[str, str],
    provided_signature: str | None,
) -> tuple[bool, str | None]:
    if not provided_signature:
        return False, "missing_signature"
    if not auth_token:
        return False, "missing_auth_token"
    expected = build_twilio_signature(auth_token, request_url, params)
    if not hmac.compare_digest(expected, provided_signature):
        return False, "invalid_signature"
    return True, None
