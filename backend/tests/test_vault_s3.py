"""Tests for S3 presigned URL generation helpers."""

from datetime import datetime, timedelta, timezone
import hashlib
import sys
from types import SimpleNamespace

import pytest

from app.services.vault_s3 import (
    ArtifactObjectMetadata,
    S3ObjectKeyValidationError,
    S3PresignConfigurationError,
    S3PresignGenerationError,
    generate_presigned_download_url,
)


class _FakeS3Client:
    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):  # noqa: N803
        assert ClientMethod == "get_object"
        assert Params["Bucket"] == "bucket"
        assert Params["Key"] == "orgs/org-1/incidents/inc-1/artifacts/art-1.zip"
        # caller asked for 900, implementation caps to 300 for short-lived URL issuance
        assert ExpiresIn == 300
        return "https://signed.example.com/exports/test.zip"


def test_generate_presigned_download_url_missing_bucket_raises():
    with pytest.raises(S3PresignConfigurationError, match="Export download bucket is not configured"):
        generate_presigned_download_url(
            bucket="",
            key="orgs/org-1/incidents/inc-1/artifacts/art-1.zip",
            region="us-east-1",
        )


def test_generate_presigned_download_url_invalid_key_raises():
    with pytest.raises(S3ObjectKeyValidationError):
        generate_presigned_download_url(
            bucket="bucket",
            key="org/org-1/incidents/inc-1/exports/test.zip",
            region="us-east-1",
        )


def test_generate_presigned_download_url_uses_boto3(monkeypatch):
    fake_boto3 = SimpleNamespace(client=lambda *_args, **_kwargs: _FakeS3Client())
    fake_botocore_exceptions = SimpleNamespace(
        BotoCoreError=Exception,
        ClientError=Exception,
    )

    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)

    url = generate_presigned_download_url(
        bucket="bucket",
        key="orgs/org-1/incidents/inc-1/artifacts/art-1.zip",
        region="us-east-1",
        expires_in=900,
    )

    assert url == "https://signed.example.com/exports/test.zip"


def test_generate_presigned_download_url_missing_boto3_raises(monkeypatch):
    monkeypatch.delitem(sys.modules, "boto3", raising=False)

    original_import = __import__

    def _raising_import(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("No module named boto3")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raising_import)

    with pytest.raises(S3PresignGenerationError, match="Failed to generate download URL"):
        generate_presigned_download_url(
            bucket="bucket",
            key="orgs/org-1/incidents/inc-1/artifacts/art-1.zip",
            region="us-east-1",
        )


def test_artifact_metadata_round_trip_and_s3_projection():
    data = b"artifact-bytes"
    captured_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    uploaded_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

    metadata = ArtifactObjectMetadata.from_blob(
        data=data,
        content_type="application/pdf",
        captured_at_utc=captured_at,
        uploaded_at_utc=uploaded_at,
    )

    metadata.validate_against_data(data)
    headers = metadata.to_s3_metadata()

    assert headers["adc-sha256"] == hashlib.sha256(data).hexdigest()
    assert headers["adc-byte-size"] == str(len(data))
    assert headers["adc-content-type"] == "application/pdf"
    assert headers["adc-captured-at-utc"] == captured_at.isoformat()
    assert headers["adc-uploaded-at-utc"] == uploaded_at.isoformat()


def test_artifact_metadata_rejects_timestamp_inversion():
    metadata = ArtifactObjectMetadata(
        sha256="a" * 64,
        byte_size=1,
        content_type="video/mp4",
        captured_at_utc=datetime.now(timezone.utc),
        uploaded_at_utc=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="before capture"):
        metadata.validate()
