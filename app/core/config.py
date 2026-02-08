"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql://localhost/adc_mvp"
    REDIS_URL: str = "redis://localhost:6379/0"
    SAMSARA_API_KEY: str = ""
    S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"
    DEBUG: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
