"""Application configuration."""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_ENV: str = "dev"

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

        return self

    class Config:
        env_file = ".env"


settings = Settings()
