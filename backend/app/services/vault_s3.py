"""Vault / S3 storage service."""

import logging

logger = logging.getLogger(__name__)


class S3PresignConfigurationError(ValueError):
    """Raised when required S3 presign configuration is missing."""


class S3PresignGenerationError(RuntimeError):
    """Raised when generating an S3 presigned URL fails."""


class VaultS3:
    """Handles storing and retrieving artifacts from S3."""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region

    def put_bytes(self, key: str, data: bytes) -> str:
        """Upload data to S3 and return the storage path."""
        path = f"s3://{self.bucket}/{key}"
        logger.info("Uploading to %s", path)
        # Placeholder: integrate boto3
        return path

    def get_bytes(self, key: str) -> bytes:
        """Download data from S3."""
        logger.info("Downloading s3://%s/%s", self.bucket, key)
        # Placeholder: integrate boto3
        return b""

    def presign_download(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned URL for downloading the object."""
        return generate_presigned_download_url(
            bucket=self.bucket,
            key=key,
            region=self.region,
            expires_in=expires_in,
        )

    def upload(self, key: str, data: bytes) -> str:
        """Backward-compatible alias for put_bytes."""
        return self.put_bytes(key, data)

    def download(self, key: str) -> bytes:
        """Backward-compatible alias for get_bytes."""
        return self.get_bytes(key)


def generate_presigned_download_url(
    *,
    bucket: str,
    key: str,
    region: str,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned S3 download URL using boto3."""
    if not bucket:
        raise S3PresignConfigurationError("Export download bucket is not configured")
    if not key:
        raise S3PresignConfigurationError("Export download object key is not configured")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        client = boto3.client("s3", region_name=region)
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except ImportError as exc:
        logger.exception("boto3 is required to generate S3 presigned URLs")
        raise S3PresignGenerationError("Failed to generate download URL") from exc
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Failed to generate presigned S3 URL")
        raise S3PresignGenerationError("Failed to generate download URL") from exc
