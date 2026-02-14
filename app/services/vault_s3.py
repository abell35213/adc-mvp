"""Vault / S3 storage service.

This module defines a very simple wrapper around object storage.
The original ADC MVP used a similar service to abstract away
integration with Amazon S3. Here we preserve that interface so that
other parts of the system (e.g. evidence tasks and export tasks)
can remain unchanged when the storage backend evolves.

At the moment this implementation is merely a placeholder: it does
not actually integrate with AWS and instead returns deterministic
paths and empty byte strings. In a production deployment you
should replace the body of these methods with calls to `boto3` or
another S3-compatible library, handle exceptions appropriately and
configure authentication via environment variables or IAM roles.
"""

import logging

logger = logging.getLogger(__name__)


class VaultS3:
    """Handles storing and retrieving artifacts from S3.

    The constructor takes a bucket name and an optional region. These
    values are used to construct URIs and presigned URLs. No network
    calls are made until the methods `put_bytes` or `get_bytes` are
    invoked.

    Note that this class is intentionally simplistic: it does not
    perform any concurrency control, multipart uploads or retries. If
    your application needs to handle large objects or intermittent
    network conditions, consider wrapping this service with a more
    sophisticated client.
    """

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        self.bucket = bucket
        self.region = region

    def put_bytes(self, key: str, data: bytes) -> str:
        """Upload data to S3 and return the storage path.

        Args:
            key: The S3 object key (i.e. path within the bucket).
            data: A bytes-like object containing the content to upload.

        Returns:
            A URI-like string (e.g. ``s3://bucket/key``) representing
            the location of the uploaded object. In the current
            placeholder implementation this is constructed without
            performing any network call.
        """
        path = f"s3://{self.bucket}/{key}"
        logger.info("Uploading to %s", path)
        # TODO: integrate boto3 here for real uploads
        return path

    def get_bytes(self, key: str) -> bytes:
        """Download data from S3.

        Args:
            key: The S3 object key (i.e. path within the bucket).

        Returns:
            The bytes content of the object. In this placeholder
            implementation an empty bytes object is returned. In a
            production setting you should fetch the object from S3
            using a client such as boto3 and return its contents.
        """
        logger.info("Downloading s3://%s/%s", self.bucket, key)
        # TODO: integrate boto3 here for real downloads
        return b""

    def presign_download(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned URL for downloading the object.

        Args:
            key: The S3 object key for which to generate the URL.
            expires_in: Time in seconds until the URL expires.

        Returns:
            A URL that can be used to download the object. For this
            placeholder implementation we fabricate a URL following
            Amazon's standard format. In a real implementation you
            would call ``boto3.client('s3').generate_presigned_url(...)``.
        """
        return (
            f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"  # noqa: E501
            f"?X-Amz-Expires={expires_in}"
        )

    # Backwards compatibility aliases
    def upload(self, key: str, data: bytes) -> str:
        """Backward-compatible alias for ``put_bytes``."""
        return self.put_bytes(key, data)

    def download(self, key: str) -> bytes:
        """Backward-compatible alias for ``get_bytes``."""
        return self.get_bytes(key)