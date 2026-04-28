"""Application configuration models and environment-aware loader."""

from __future__ import annotations

import json
import os
from typing import Any, ClassVar

import boto3
from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

INSECURE_DEFAULT_SENTINEL = "change-me-in-production"
# Additional well-known placeholder strings published in the various .env.example
# templates. Any of these values must be rejected outside of local dev so that an
# operator who copies an example file verbatim cannot accidentally ship insecure
# secrets to staging or prod.
INSECURE_PLACEHOLDER_VALUES = frozenset(
    {INSECURE_DEFAULT_SENTINEL, "__CHANGE_ME__", "changeme"}
)
LOCAL_DATABASE_DEFAULT = "postgresql://localhost/adc_mvp"
LOCAL_REDIS_DEFAULT = "redis://localhost:6379/0"


def _looks_like_insecure_placeholder(value: str) -> bool:
    """True when *value* is one of the well-known placeholder strings."""
    return value.strip() in INSECURE_PLACEHOLDER_VALUES


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
            raise ValueError("AWS Secrets Manager secret must contain SecretString JSON payload")

        try:
            decoded = json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise ValueError("AWS Secrets Manager secret payload must be valid JSON") from exc

        if not isinstance(decoded, dict):
            raise ValueError("AWS Secrets Manager secret payload must decode to an object")

        return {str(k): v for k, v in decoded.items()}


class AppSettings(BaseSettings):
    """Base application settings loaded from environment variables."""

    APP_ENV: str = "local"

    # Secret loading strategy
    SECRET_PROVIDER: str = "env"
    AWS_SECRETS_MANAGER_SECRET_ID: str = ""
    AWS_SECRETS_MANAGER_REGION: str = "us-east-1"
    AWS_SECRETS_MANAGER_VERSION_STAGE: str = "AWSCURRENT"

    DATABASE_URL: str = LOCAL_DATABASE_DEFAULT
    REDIS_URL: str = LOCAL_REDIS_DEFAULT
    SAMSARA_API_KEY: str = ""
    S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_ARTIFACTS_BUCKET: str = "adc-mvp-artifacts"
    S3_EXPORTS_BUCKET: str = "adc-mvp-exports"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Observability
    RELEASE: str = "dev"
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    METRICS_BACKEND: str = "inmemory"

    # CORS / Cookies
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    COOKIE_HTTPONLY: bool = True
    COOKIE_SECURE: bool = False
    COOKIE_DEPLOYMENT_TOPOLOGY: str = "same_site"

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
    OTP_HASH_PEPPER: str = INSECURE_DEFAULT_SENTINEL
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_REQUEST_RATE_LIMIT: int = 5
    OTP_VERIFY_RATE_LIMIT: int = 10
    OTP_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # Auth / JWT
    JWT_SECRET_KEY: str = INSECURE_DEFAULT_SENTINEL
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    EXPORT_DOWNLOAD_URL_EXPIRES_SECONDS: int = 300
    ORG_ADMIN_MFA_REQUIRED: bool = False

    # API rate limits (per subject/IP sliding windows)
    AUTH_LOGIN_RATE_LIMIT: int = 20
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 300
    EXPORT_REQUEST_RATE_LIMIT: int = 20
    EXPORT_RATE_LIMIT_WINDOW_SECONDS: int = 300
    DRIVER_UPLOAD_URL_RATE_LIMIT: int = 30
    DRIVER_UPLOAD_URL_RATE_LIMIT_WINDOW_SECONDS: int = 300
    DRIVER_QR_RESOLVE_RATE_LIMIT: int = 60
    DRIVER_QR_RESOLVE_RATE_LIMIT_WINDOW_SECONDS: int = 300

    ENV_NAME: ClassVar[str] = "local"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            AwsSecretsManagerSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def cookie_samesite(self) -> str:
        return "none" if self.COOKIE_DEPLOYMENT_TOPOLOGY == "cross_site" else "lax"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    def _prod_validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.is_prod:
            return errors

        if _looks_like_insecure_placeholder(self.JWT_SECRET_KEY):
            errors.append("JWT_SECRET_KEY cannot use development default in prod")
        if _looks_like_insecure_placeholder(self.OTP_HASH_PEPPER):
            errors.append("OTP_HASH_PEPPER cannot use development default in prod")
        if self.DATABASE_URL.strip() == LOCAL_DATABASE_DEFAULT:
            errors.append("DATABASE_URL cannot use development default in prod")
        if not self.COOKIE_HTTPONLY:
            errors.append("COOKIE_HTTPONLY must be true in prod")
        if not self.COOKIE_SECURE:
            errors.append("COOKIE_SECURE must be true in prod")
        if self.COOKIE_DEPLOYMENT_TOPOLOGY == "cross_site" and not self.COOKIE_SECURE:
            errors.append("cross_site cookies require COOKIE_SECURE=true")
        for key, value in (
            ("FRONTEND_ORIGIN", self.FRONTEND_ORIGIN),
            ("PUBLIC_APP_BASE_URL", self.PUBLIC_APP_BASE_URL),
        ):
            if value.strip().lower().startswith("http://localhost"):
                errors.append(f"{key} cannot point to localhost over http in prod")
        return errors

    def validate_production_invariants(self) -> None:
        """Backwards-compatible production-only validations."""
        errors = self._prod_validation_errors()
        if errors:
            raise ValueError(f"Invalid prod configuration: {'; '.join(errors)}")

    @model_validator(mode="after")
    def validate_environment(self):
        self.APP_ENV = self.APP_ENV.strip().lower()
        if self.APP_ENV == "dev":
            self.APP_ENV = "local"

        if self.APP_ENV not in {"local", "test", "staging", "prod"}:
            raise ValueError("APP_ENV must be one of: local, test, staging, prod")

        self.SECRET_PROVIDER = self.SECRET_PROVIDER.strip().lower()
        if self.SECRET_PROVIDER not in {"env", "aws_secrets_manager"}:
            raise ValueError("SECRET_PROVIDER must be one of: env, aws_secrets_manager")

        self.COOKIE_DEPLOYMENT_TOPOLOGY = self.COOKIE_DEPLOYMENT_TOPOLOGY.strip().lower()
        if self.COOKIE_DEPLOYMENT_TOPOLOGY not in {"same_site", "cross_site"}:
            raise ValueError("COOKIE_DEPLOYMENT_TOPOLOGY must be one of: same_site, cross_site")

        if not 60 <= self.EXPORT_DOWNLOAD_URL_EXPIRES_SECONDS <= 900:
            raise ValueError("EXPORT_DOWNLOAD_URL_EXPIRES_SECONDS must be between 60 and 900")

        self.METRICS_BACKEND = self.METRICS_BACKEND.strip().lower()
        if self.METRICS_BACKEND not in {"inmemory", "prometheus", "opentelemetry", "otel", "datadog"}:
            raise ValueError(
                "METRICS_BACKEND must be one of: inmemory, prometheus, opentelemetry, otel, datadog"
            )

        if not 0.0 <= self.SENTRY_TRACES_SAMPLE_RATE <= 1.0:
            raise ValueError("SENTRY_TRACES_SAMPLE_RATE must be between 0.0 and 1.0")

        self.RELEASE = self.RELEASE.strip() or "dev"

        return self

    model_config = SettingsConfigDict(env_file=".env")


class LocalSettings(AppSettings):
    ENV_NAME: ClassVar[str] = "local"
    APP_ENV: str = "local"
    DEBUG: bool = True


class TestSettings(AppSettings):
    ENV_NAME: ClassVar[str] = "test"
    APP_ENV: str = "test"


class StagingSettings(AppSettings):
    ENV_NAME: ClassVar[str] = "staging"
    APP_ENV: str = "staging"


class ProdSettings(AppSettings):
    ENV_NAME: ClassVar[str] = "prod"
    APP_ENV: str = "prod"


def build_settings(app_env: str | None = None) -> AppSettings:
    """Create explicit settings class by environment."""
    resolved_env = app_env if app_env is not None else os.getenv("APP_ENV")
    normalized = (resolved_env or "local").strip().lower()
    if normalized == "dev":
        normalized = "local"

    settings_cls: type[AppSettings]
    if normalized == "local":
        settings_cls = LocalSettings
    elif normalized == "test":
        settings_cls = TestSettings
    elif normalized == "staging":
        settings_cls = StagingSettings
    elif normalized == "prod":
        settings_cls = ProdSettings
    else:
        raise ValueError("APP_ENV must be one of: local, test, staging, prod")

    return settings_cls()


Settings = AppSettings
settings = build_settings()
