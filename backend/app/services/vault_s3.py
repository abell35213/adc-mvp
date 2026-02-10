"""Vault / S3 storage service."""

import logging

logger = logging.getLogger(__name__)


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
        return (
            f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
            f"?X-Amz-Expires={expires_in}"
        )

    def upload(self, key: str, data: bytes) -> str:
        """Backward-compatible alias for put_bytes."""
        return self.put_bytes(key, data)

    def download(self, key: str) -> bytes:
        """Backward-compatible alias for get_bytes."""
        return self.get_bytes(key)
