"""Helpers for scrubbing sensitive values from logs and error payloads."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_CLASS_A_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "jwt_secret_key",
        "otp_hash_pepper",
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "token",
        "bearer_token",
    }
)
SENSITIVE_CLASS_B_KEYS = frozenset({"otp_code", "mfa_code", "note", "notes", "narrative"})

_RE_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9\-._~+/]+=*")
_RE_SECRET_ASSIGN = re.compile(
    r"(?i)\b(password|secret|api[_-]?key|token|authorization)\b\s*([:=])\s*([^\s,;]+)"
)
_RE_OTP_INLINE = re.compile(
    r"(?i)\b(otp(?:_code)?|mfa(?:_code)?|verification(?:_code)?)\b([^\d]{0,20})(\d{4,8})"
)
_RE_NOTE_KV = re.compile(r"(?i)\b(note|notes|narrative)\b\s*([:=])\s*([^,;\n]+)")


REDACTED = "[REDACTED]"
REDACTED_OTP = "[REDACTED_OTP]"
REDACTED_NOTE = "[REDACTED_NOTE]"


def _redact_string(text: str) -> str:
    value = _RE_BEARER.sub("Bearer [REDACTED]", text)
    value = _RE_SECRET_ASSIGN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", value)
    value = _RE_OTP_INLINE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED_OTP}", value)
    value = _RE_NOTE_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED_NOTE}", value)
    return value


def redact_log_data(value: Any, *, key: str | None = None) -> Any:
    """Recursively sanitize sensitive values before they are logged."""
    lowered_key = (key or "").lower()
    if lowered_key in SENSITIVE_CLASS_A_KEYS:
        return REDACTED
    if lowered_key in SENSITIVE_CLASS_B_KEYS:
        return REDACTED_NOTE if lowered_key in {"note", "notes", "narrative"} else REDACTED_OTP

    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, dict):
        return {k: redact_log_data(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_log_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_log_data(item) for item in value)
    return value
