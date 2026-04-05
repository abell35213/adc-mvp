"""Application configuration."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)


class AwsSecretsManagerSettingsSource(PydanticBaseSettingsSource):
    """Load settings from AWS Secrets Manager when enabled."""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._data = self._load_secret_data()

    def get_field_value(self, field, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data

    def _load_secret_data(self) -> dict[str, Any]:
        provider = os.getenv("SECRET_PROVIDER", "env").strip().lower()
        if provider != "aws_secrets_manager":
            return {}

        secret_id = os.getenv("AWS_SECRETS_MANAGER_SECRET_ID", "").strip()
        if not secret_id:
            raise ValueError(
                "AWS_SECRETS_MANAGER_SECRET_ID must be set when "
                "SECRET_PROVIDER=aws_secrets_manager"
            )

        region = os.getenv("AWS_SECRETS_MANAGER_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        version_stage = os.getenv("AWS_SECRETS_MANAGER_VERSION_STAGE", "AWSCURRENT")

        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id, VersionStage=version_stage)

        secret_string = response.get("SecretString", "")
        if not secret_string:
            raise ValueError(
                "AWS Secrets Manager secret must contain SecretString JSON payload"
            )

        try:
            decoded = json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "AWS Secrets Manager secret payload must be valid JSON"
            ) from exc

        if not isinstance(decoded, dict):
            raise ValueError("AWS Secrets Manager secret payload must decode to an object")

        return {str(k): v for k, v in decoded.items()}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_ENV: str = "dev"

    # Secret loading strategy
    SECRET_PROVIDER: str = "env"
    AWS_SECRETS_MANAGER_SECRET_ID: str = ""
    AWS_SECRETS_MANAGER_REGION: str = "us-east-1"
    AWS_SECRETS_MANAGER_VERSION_STAGE: str = "AWSCURRENT"

    DATABASE_URL: str = "postgresql://localhost/adc_mvp"
    REDIS_URL: str = "redis://localhost:6379/0"
    SAMSARA_API_KEY: str = ""
    S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_ARTIFACTS_BUCKET: str = "adc-mvp-artifacts"
    S3_EXPORTS_BUCKET: str = "adc-mvp-exports"
    DEBUG: bool = False

    # CORS / Cookies
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    COOKIE_SECURE: bool = False

    # Vault (filesystem)
    STORAGE_BACKEND: str = "s3"
    VAULT_ROOT: str = "/var/adc/vault"

    # Public URL / Deep-link
    PUBLIC_APP_BASE_URL: str = "http://localhost:3000"
    DRIVER_APP_DEEPLINK_SCHEME: str = "adc"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_VERIFY_SERVICE_SID: str = ""
    TWILIO_SMS_FROM: str = ""
    TWILIO_VOICE_FROM: str = ""

    # Driver OTP
    OTP_HASH_PEPPER: str = "change-me-in-production"
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_REQUEST_RATE_LIMIT: int = 5
    OTP_VERIFY_RATE_LIMIT: int = 10
    OTP_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # Auth / JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Explicit constructor args / env vars always win over remote secrets.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            AwsSecretsManagerSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    def _prod_validation_errors(self) -> list[str]:
        errors: list[str] = []

        required_secrets = {
            "JWT_SECRET_KEY": self.JWT_SECRET_KEY,
            "OTP_HASH_PEPPER": self.OTP_HASH_PEPPER,
            "DATABASE_URL": self.DATABASE_URL,
        }
        insecure_defaults = {
            "JWT_SECRET_KEY": "change-me-in-production",
            "OTP_HASH_PEPPER": "change-me-in-production",
            "DATABASE_URL": "postgresql://localhost/adc_mvp",
        }

        for key, value in required_secrets.items():
            normalized = value.strip()
            if not normalized:
                errors.append(f"{key} must be set in prod")
                continue
            if normalized == insecure_defaults[key]:
                errors.append(f"{key} cannot use development default in prod")

        if not self.COOKIE_SECURE:
            errors.append("COOKIE_SECURE must be true in prod")

        for key, value in (
            ("FRONTEND_ORIGIN", self.FRONTEND_ORIGIN),
            ("PUBLIC_APP_BASE_URL", self.PUBLIC_APP_BASE_URL),
        ):
            if value.strip().lower().startswith("http://localhost"):
                errors.append(f"{key} cannot point to localhost over http in prod")

        return errors

    def validate_production_invariants(self) -> None:
        """Raise if production configuration invariants are violated."""

        if not self.is_prod:
            return

        errors = self._prod_validation_errors()
        if errors:
            joined = "; ".join(errors)
            raise ValueError(f"Invalid prod configuration: {joined}")

    @model_validator(mode="after")
    def validate_environment(self):
        self.APP_ENV = self.APP_ENV.strip().lower()
        if self.APP_ENV not in {"dev", "staging", "prod"}:
            raise ValueError("APP_ENV must be one of: dev, staging, prod")

        self.SECRET_PROVIDER = self.SECRET_PROVIDER.strip().lower()
        if self.SECRET_PROVIDER not in {"env", "aws_secrets_manager"}:
            raise ValueError("SECRET_PROVIDER must be one of: env, aws_secrets_manager")

        return self

    class Config:
        env_file = ".env"


settings = Settings()
