"""Tests for environment configuration validation."""

import pytest

from app.core.config import Settings


class TestSettingsValidation:
    def test_prod_requires_non_default_secrets(self):
        settings = Settings(
            APP_ENV="prod",
            JWT_SECRET_KEY="change-me-in-production",
            OTP_HASH_PEPPER="change-me-in-production",
            DATABASE_URL="postgresql://localhost/adc_mvp",
            COOKIE_SECURE=True,
            FRONTEND_ORIGIN="https://app.example.com",
            PUBLIC_APP_BASE_URL="https://app.example.com",
        )

        with pytest.raises(ValueError, match="Invalid prod configuration"):
            settings.validate_production_invariants()

    def test_prod_rejects_insecure_cookie_and_localhost_urls(self):
        settings = Settings(
            APP_ENV="prod",
            JWT_SECRET_KEY="super-secret",
            OTP_HASH_PEPPER="pepper-secret",
            DATABASE_URL="postgresql://db.example.com/adc",
            COOKIE_SECURE=False,
            FRONTEND_ORIGIN="http://localhost:3000",
            PUBLIC_APP_BASE_URL="http://localhost:3000",
        )

        with pytest.raises(ValueError, match="COOKIE_SECURE must be true in prod"):
            settings.validate_production_invariants()

    def test_non_prod_allows_local_defaults(self):
        settings = Settings(APP_ENV="dev")

        settings.validate_production_invariants()

    def test_invalid_app_env_fails(self):
        with pytest.raises(ValueError, match="APP_ENV must be one of"):
            Settings(APP_ENV="production")
