"""Startup configuration validation helpers."""

from __future__ import annotations

from app.config.settings import (
    LOCAL_DATABASE_DEFAULT,
    LOCAL_REDIS_DEFAULT,
    AppSettings,
    _looks_like_insecure_placeholder,
)


def _require_non_empty(value: str) -> bool:
    return bool(value and value.strip())


def validate_startup_config(settings: AppSettings) -> None:
    """Fail fast on unsafe configuration in non-local environments."""

    errors: list[str] = []

    if not settings.is_local:
        critical_required = {
            "DATABASE_URL": settings.DATABASE_URL,
            "REDIS_URL": settings.REDIS_URL,
            "S3_ARTIFACTS_BUCKET": settings.S3_ARTIFACTS_BUCKET,
            "S3_EXPORTS_BUCKET": settings.S3_EXPORTS_BUCKET,
            "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
            "TWILIO_VERIFY_SERVICE_SID": settings.TWILIO_VERIFY_SERVICE_SID,
            "SAMSARA_API_KEY": settings.SAMSARA_API_KEY,
            "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
            "OTP_HASH_PEPPER": settings.OTP_HASH_PEPPER,
        }
        for key, value in critical_required.items():
            if not _require_non_empty(value):
                errors.append(f"{key} must be set outside local")

        if settings.DATABASE_URL.strip() == LOCAL_DATABASE_DEFAULT:
            errors.append("DATABASE_URL cannot use local default outside local")
        if settings.REDIS_URL.strip() == LOCAL_REDIS_DEFAULT:
            errors.append("REDIS_URL cannot use local default outside local")

    if settings.is_prod:
        if _looks_like_insecure_placeholder(settings.JWT_SECRET_KEY):
            errors.append("JWT_SECRET_KEY cannot use insecure default in prod")
        if _looks_like_insecure_placeholder(settings.OTP_HASH_PEPPER):
            errors.append("OTP_HASH_PEPPER cannot use insecure default in prod")

        if not settings.COOKIE_HTTPONLY:
            errors.append("COOKIE_HTTPONLY must be true in prod")
        if not settings.COOKIE_SECURE:
            errors.append("COOKIE_SECURE must be true in prod")

        if settings.COOKIE_DEPLOYMENT_TOPOLOGY == "cross_site" and not settings.COOKIE_SECURE:
            errors.append("cross_site cookies require COOKIE_SECURE=true")

        for key, value in (
            ("FRONTEND_ORIGIN", settings.FRONTEND_ORIGIN),
            ("PUBLIC_APP_BASE_URL", settings.PUBLIC_APP_BASE_URL),
        ):
            normalized = value.strip().lower()
            if normalized.startswith("http://localhost"):
                errors.append(f"{key} cannot point to localhost over http in prod")

    if errors:
        raise ValueError(f"Invalid configuration: {'; '.join(errors)}")

    # Soft warning (logged, non-fatal): FMCSA pull enabled in prod with
    # no Socrata app token will hit the anonymous rate limit hard.
    if (
        settings.is_prod
        and settings.FMCSA_INSPECTIONS_ENABLED
        and not _require_non_empty(settings.SOCRATA_APP_TOKEN)
    ):
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "FMCSA_INSPECTIONS_ENABLED=true but SOCRATA_APP_TOKEN is empty; "
            "anonymous Socrata requests are rate-limited and may be throttled."
        )
