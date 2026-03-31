"""Tests for S3 presigned URL generation helpers."""

import sys
from types import SimpleNamespace

from app.services.vault_s3 import (
    S3PresignConfigurationError,
    S3PresignGenerationError,
    generate_presigned_download_url,
)


class _FakeS3Client:
    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):  # noqa: N803
        assert ClientMethod == "get_object"
        assert Params["Bucket"] == "bucket"
        assert Params["Key"] == "exports/test.zip"
        assert ExpiresIn == 900
        return "https://signed.example.com/exports/test.zip"


def test_generate_presigned_download_url_missing_bucket_raises():
    try:
        generate_presigned_download_url(
            bucket="",
            key="exports/test.zip",
            region="us-east-1",
        )
    except S3PresignConfigurationError as exc:
        assert str(exc) == "Export download bucket is not configured"
    else:
        raise AssertionError("Expected S3PresignConfigurationError")


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
        key="exports/test.zip",
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

    try:
        generate_presigned_download_url(
            bucket="bucket",
            key="exports/test.zip",
            region="us-east-1",
        )
    except S3PresignGenerationError as exc:
        assert str(exc) == "Failed to generate download URL"
    else:
        raise AssertionError("Expected S3PresignGenerationError")
