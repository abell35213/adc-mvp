"""Vault / S3 storage service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PRESIGN_TTL_SECONDS = 300
MAX_PRESIGN_TTL_SECONDS = 300
_PRIVATE_KEY_PATTERN = re.compile(
    r"^orgs/[A-Za-z0-9._-]+/incidents/[A-Za-z0-9._-]+/artifacts/[A-Za-z0-9._-]+(?:\.[A-Za-z0-9]+)?$"
)
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class S3PresignConfigurationError(ValueError):
    """Raised when required S3 presign configuration is missing."""


class S3PresignGenerationError(RuntimeError):
    """Raised when generating an S3 presigned URL fails."""


class S3ObjectKeyValidationError(ValueError):
    """Raised when an S3 object key does not follow private key conventions."""


class S3UploadError(RuntimeError):
    """Raised when uploading an object to S3 fails."""


class S3DownloadError(RuntimeError):
    """Raised when downloading an object from S3 fails."""


@dataclass(frozen=True)
class ArtifactObjectMetadata:
    """Integrity-critical metadata stored alongside an artifact blob."""

    sha256: str
    byte_size: int
    content_type: str
    captured_at_utc: datetime
    uploaded_at_utc: datetime

    @classmethod
    def from_blob(
        cls,
        *,
        data: bytes,
        content_type: str,
        captured_at_utc: datetime,
        uploaded_at_utc: datetime | None = None,
    ) -> "ArtifactObjectMetadata":
        """Build validated metadata from raw bytes."""
        return cls(
            sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            content_type=content_type,
            captured_at_utc=captured_at_utc,
            uploaded_at_utc=uploaded_at_utc or datetime.now(timezone.utc),
        )

    def validate(self) -> None:
        """Validate metadata fields for audit/integrity usage."""
        if not _SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError("Artifact metadata sha256 must be a lowercase hex SHA-256 digest")
        if self.byte_size < 0:
            raise ValueError("Artifact metadata byte_size must be non-negative")
        if not self.content_type or "/" not in self.content_type:
            raise ValueError("Artifact metadata content_type is invalid")
        if self.captured_at_utc.tzinfo is None or self.uploaded_at_utc.tzinfo is None:
            raise ValueError("Artifact metadata timestamps must be timezone-aware")
        if self.uploaded_at_utc < self.captured_at_utc:
            raise ValueError("Artifact upload timestamp cannot be before capture timestamp")

    def validate_against_data(self, data: bytes) -> None:
        """Validate metadata plus byte-level integrity against provided bytes."""
        self.validate()
        if self.byte_size != len(data):
            raise ValueError("Artifact metadata byte_size does not match payload size")
        if self.sha256 != hashlib.sha256(data).hexdigest():
            raise ValueError("Artifact metadata sha256 does not match payload")

    def to_s3_metadata(self) -> dict[str, str]:
        """Convert validated metadata to S3-compatible metadata map."""
        self.validate()
        return {
            "adc-sha256": self.sha256,
            "adc-byte-size": str(self.byte_size),
            "adc-content-type": self.content_type,
            "adc-captured-at-utc": self.captured_at_utc.isoformat(),
            "adc-uploaded-at-utc": self.uploaded_at_utc.isoformat(),
        }


class VaultS3:
    """Handles storing and retrieving artifacts from S3."""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region

    def put_bytes(
        self,
        key: str,
        data: bytes,
        metadata: ArtifactObjectMetadata | None = None,
    ) -> str:
        """Upload data to S3 and return the storage path."""
        _validate_private_object_key(key)
        if metadata is not None:
            metadata.validate_against_data(data)
        path = f"s3://{self.bucket}/{key}"

        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key, "Body": data}
        if metadata is not None:
            params["Metadata"] = metadata.to_s3_metadata()
            params["ContentType"] = metadata.content_type

        try:
            client = _build_s3_client(self.region)
            client.put_object(**params)
        except ImportError as exc:
            logger.exception("boto3 is required to upload artifacts to S3")
            raise S3UploadError(f"Failed to upload object to {path}") from exc
        except _boto_client_errors() as exc:
            logger.exception("Failed to upload object to %s", path)
            raise S3UploadError(f"Failed to upload object to {path}") from exc

        logger.info("Uploaded to %s", path)
        return path

    def get_bytes(self, key: str) -> bytes:
        """Download data from S3."""
        _validate_private_object_key(key)
        path = f"s3://{self.bucket}/{key}"

        try:
            client = _build_s3_client(self.region)
            response = client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            try:
                data = body.read()
            finally:
                close = getattr(body, "close", None)
                if callable(close):
                    close()
        except ImportError as exc:
            logger.exception("boto3 is required to download artifacts from S3")
            raise S3DownloadError(f"Failed to download object from {path}") from exc
        except _boto_client_errors() as exc:
            logger.exception("Failed to download object from %s", path)
            raise S3DownloadError(f"Failed to download object from {path}") from exc

        logger.info("Downloaded from %s", path)
        return data

    def presign_download(
        self,
        key: str,
        expires_in: int = DEFAULT_PRESIGN_TTL_SECONDS,
    ) -> str:
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


def _validate_private_object_key(key: str) -> None:
    if not key:
        raise S3ObjectKeyValidationError("S3 object key is required")
    if not _PRIVATE_KEY_PATTERN.fullmatch(key):
        raise S3ObjectKeyValidationError(
            "S3 object key must match orgs/{org_id}/incidents/{incident_id}/artifacts/{artifact_id}"
        )


def _build_s3_client(region: str) -> Any:
    """Construct a boto3 S3 client for the given region.

    boto3 is imported lazily so this module still imports in environments where
    the dependency is absent; callers translate a missing import into a
    domain-specific upload/download error.
    """
    import boto3

    return boto3.client("s3", region_name=region)


def _boto_client_errors() -> tuple[type[BaseException], ...]:
    """Return the botocore exception classes to catch around S3 calls.

    Returns an empty tuple if botocore is unavailable so the surrounding
    ``ImportError`` handler reports the missing dependency instead.
    """
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        return ()
    return (ClientError, BotoCoreError)


def _enforce_short_presign_ttl(expires_in: int) -> int:
    if expires_in <= 0:
        raise S3PresignConfigurationError("Export download URL TTL must be positive")
    return min(expires_in, MAX_PRESIGN_TTL_SECONDS)


def generate_presigned_download_url(
    *,
    bucket: str,
    key: str,
    region: str,
    expires_in: int = DEFAULT_PRESIGN_TTL_SECONDS,
) -> str:
    """Generate a presigned S3 download URL using boto3."""
    if not bucket:
        raise S3PresignConfigurationError("Export download bucket is not configured")

    _validate_private_object_key(key)
    ttl = _enforce_short_presign_ttl(expires_in)

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        client = boto3.client("s3", region_name=region)
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl,
        )
    except ImportError as exc:
        logger.exception("boto3 is required to generate S3 presigned URLs")
        raise S3PresignGenerationError("Failed to generate download URL") from exc
    except (ClientError, BotoCoreError) as exc:
        logger.exception("Failed to generate presigned S3 URL")
        raise S3PresignGenerationError("Failed to generate download URL") from exc
