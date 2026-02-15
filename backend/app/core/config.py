"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    # Auth / JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
