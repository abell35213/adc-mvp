"""Tests for environment configuration validation."""

import json

import pytest

from app.config.validation import validate_startup_config
from app.core.config import Settings


class TestSettingsValidation:
    def _non_local_minimum(self) -> dict[str, str | bool]:
        return {
            "APP_ENV": "staging",
            "DATABASE_URL": "postgresql://db.example.com/adc",
            "REDIS_URL": "redis://redis.example.com:6379/0",
            "S3_ARTIFACTS_BUCKET": "adc-prod-artifacts",
            "S3_EXPORTS_BUCKET": "adc-prod-exports",
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token",
            "TWILIO_VERIFY_SERVICE_SID": "VA123",
            "SAMSARA_API_KEY": "samsara-key",
            "JWT_SECRET_KEY": "super-secret",
            "OTP_HASH_PEPPER": "pepper-secret",
            "COOKIE_SECURE": True,
            "FRONTEND_ORIGIN": "https://app.example.com",
            "PUBLIC_APP_BASE_URL": "https://app.example.com",
        }

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

    def test_non_prod_allows_local_defaults_for_legacy_validation(self):
        settings = Settings(APP_ENV="local")

        settings.validate_production_invariants()

    def test_invalid_app_env_fails(self):
        with pytest.raises(ValueError, match="APP_ENV must be one of"):
            Settings(APP_ENV="production")

    def test_invalid_secret_provider_fails(self):
        with pytest.raises(ValueError, match="SECRET_PROVIDER must be one of"):
            Settings(SECRET_PROVIDER="vault")

    def test_invalid_cookie_topology_fails(self):
        with pytest.raises(ValueError, match="COOKIE_DEPLOYMENT_TOPOLOGY"):
            Settings(COOKIE_DEPLOYMENT_TOPOLOGY="hybrid")

    def test_prod_cross_site_requires_secure_cookie(self):
        settings = Settings(
            APP_ENV="prod",
            JWT_SECRET_KEY="super-secret",
            OTP_HASH_PEPPER="pepper-secret",
            DATABASE_URL="postgresql://db.example.com/adc",
            COOKIE_HTTPONLY=True,
            COOKIE_SECURE=False,
            COOKIE_DEPLOYMENT_TOPOLOGY="cross_site",
            FRONTEND_ORIGIN="https://app.example.com",
            PUBLIC_APP_BASE_URL="https://app.example.com",
        )

        with pytest.raises(ValueError, match="cross_site cookies require COOKIE_SECURE=true"):
            settings.validate_production_invariants()

    def test_startup_validation_requires_critical_secrets_outside_local(self):
        settings = Settings(APP_ENV="staging")

        with pytest.raises(ValueError, match="must be set outside local"):
            validate_startup_config(settings)

    def test_startup_validation_accepts_complete_staging_config(self):
        settings = Settings(**self._non_local_minimum())

        validate_startup_config(settings)


class TestAwsSecretsManagerSource:
    def test_loads_runtime_settings_from_aws_secrets_manager(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeSecretsClient:
            def get_secret_value(self, SecretId: str, VersionStage: str):  # noqa: N803
                assert SecretId == "adc/runtime"
                assert VersionStage == "AWSCURRENT"
                return {
                    "SecretString": json.dumps(
                        {
                            "JWT_SECRET_KEY": "jwt-from-secret",
                            "DATABASE_URL": "postgresql://prod/db",
                            "TWILIO_AUTH_TOKEN": "token-from-secret",
                        }
                    )
                }

        monkeypatch.setenv("SECRET_PROVIDER", "aws_secrets_manager")
        monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "adc/runtime")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        monkeypatch.setattr("app.config.settings.boto3.client", lambda *args, **kwargs: FakeSecretsClient())

        settings = Settings()

        assert settings.JWT_SECRET_KEY == "jwt-from-secret"
        assert settings.DATABASE_URL == "postgresql://prod/db"
        assert settings.TWILIO_AUTH_TOKEN == "token-from-secret"

    def test_environment_overrides_aws_secret_values(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeSecretsClient:
            def get_secret_value(self, SecretId: str, VersionStage: str):  # noqa: N803
                return {
                    "SecretString": json.dumps(
                        {
                            "JWT_SECRET_KEY": "jwt-from-secret",
                            "DATABASE_URL": "postgresql://prod/db",
                        }
                    )
                }

        monkeypatch.setenv("SECRET_PROVIDER", "aws_secrets_manager")
        monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "adc/runtime")
        monkeypatch.setenv("JWT_SECRET_KEY", "jwt-from-env")
        monkeypatch.setattr("app.config.settings.boto3.client", lambda *args, **kwargs: FakeSecretsClient())

        settings = Settings()

        assert settings.JWT_SECRET_KEY == "jwt-from-env"

    def test_aws_provider_requires_secret_id(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SECRET_PROVIDER", "aws_secrets_manager")
        monkeypatch.delenv("AWS_SECRETS_MANAGER_SECRET_ID", raising=False)

        with pytest.raises(ValueError, match="AWS_SECRETS_MANAGER_SECRET_ID"):
            Settings()
