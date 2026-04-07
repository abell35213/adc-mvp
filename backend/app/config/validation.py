"""Startup configuration validation helpers."""

from __future__ import annotations

from app.core.config import Settings


def validate_startup_config(settings: Settings) -> None:
    """Fail fast on unsafe production session/cookie configuration."""
    settings.validate_production_invariants()

    if not settings.is_prod:
        return

    errors: list[str] = []
    if settings.cookie_samesite not in {"lax", "none"}:
        errors.append("cookie SameSite policy must resolve to 'lax' or 'none'")

    if settings.cookie_samesite == "none" and not settings.COOKIE_SECURE:
        errors.append("SameSite=None cookies require COOKIE_SECURE=true")

    if not settings.COOKIE_HTTPONLY:
        errors.append("COOKIE_HTTPONLY must be true for production session cookies")

    if errors:
        raise ValueError(f"Invalid prod configuration: {'; '.join(errors)}")
