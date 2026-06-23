"""Tests for S3 presigned URL generation helpers."""

from datetime import datetime, timedelta, timezone
import hashlib
import sys
from types import SimpleNamespace

import pytest

from app.services.vault_s3 import (
    ArtifactObjectMetadata,
    S3DownloadError,
    S3ObjectKeyValidationError,
    S3PresignConfigurationError,
    S3PresignGenerationError,
    S3UploadError,
    VaultS3,
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


# ── put_bytes / get_bytes S3 round-trip ─────────────────────────────

_ROUND_TRIP_KEY = "orgs/org-1/incidents/inc-1/artifacts/art-1.zip"


class _FakeBody:
    """Minimal stand-in for the botocore StreamingBody returned by get_object."""

    def __init__(self, data: bytes):
        self._data = data
        self.closed = False

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        self.closed = True


class _FakeStorageClient:
    """Records put_object calls and serves get_object from an in-memory store."""

    def __init__(self, store=None, put_error=None, get_error=None):
        self.store = store if store is not None else {}
        self.put_calls = []
        self._put_error = put_error
        self._get_error = get_error
        self.last_body = None

    def put_object(self, **kwargs):  # noqa: D401 - boto3 signature mirror
        if self._put_error is not None:
            raise self._put_error
        self.put_calls.append(kwargs)
        self.store[kwargs["Key"]] = kwargs["Body"]
        return {}

    def get_object(self, Bucket, Key):  # noqa: N803 - boto3 signature mirror
        if self._get_error is not None:
            raise self._get_error
        self.last_body = _FakeBody(self.store[Key])
        return {"Body": self.last_body}


def _install_boto3(monkeypatch, client):
    """Patch sys.modules so VaultS3's lazy boto3/botocore imports hit fakes."""
    fake_boto3 = SimpleNamespace(client=lambda *_args, **_kwargs: client)
    fake_botocore_exceptions = SimpleNamespace(
        BotoCoreError=_FakeBotoCoreError,
        ClientError=_FakeClientError,
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)


class _FakeBotoCoreError(Exception):
    pass


class _FakeClientError(Exception):
    pass


def test_put_bytes_uploads_with_metadata_and_returns_path(monkeypatch):
    client = _FakeStorageClient()
    _install_boto3(monkeypatch, client)

    data = b"court-package-bytes"
    metadata = ArtifactObjectMetadata.from_blob(
        data=data,
        content_type="application/zip",
        captured_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    path = VaultS3(bucket="bucket", region="us-east-1").put_bytes(
        _ROUND_TRIP_KEY, data, metadata=metadata
    )

    assert path == f"s3://bucket/{_ROUND_TRIP_KEY}"
    assert len(client.put_calls) == 1
    call = client.put_calls[0]
    assert call["Bucket"] == "bucket"
    assert call["Key"] == _ROUND_TRIP_KEY
    assert call["Body"] == data
    assert call["ContentType"] == "application/zip"
    assert call["Metadata"]["adc-sha256"] == hashlib.sha256(data).hexdigest()
    assert call["Metadata"]["adc-byte-size"] == str(len(data))


def test_put_bytes_without_metadata_omits_metadata_headers(monkeypatch):
    client = _FakeStorageClient()
    _install_boto3(monkeypatch, client)

    VaultS3(bucket="bucket").put_bytes(_ROUND_TRIP_KEY, b"raw-bytes")

    call = client.put_calls[0]
    assert "Metadata" not in call
    assert "ContentType" not in call


def test_put_bytes_rejects_invalid_key(monkeypatch):
    client = _FakeStorageClient()
    _install_boto3(monkeypatch, client)

    with pytest.raises(S3ObjectKeyValidationError):
        VaultS3(bucket="bucket").put_bytes("not/a/valid/key", b"data")

    assert client.put_calls == []


def test_put_bytes_rejects_metadata_payload_mismatch(monkeypatch):
    client = _FakeStorageClient()
    _install_boto3(monkeypatch, client)

    metadata = ArtifactObjectMetadata.from_blob(
        data=b"original",
        content_type="application/zip",
        captured_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError):
        VaultS3(bucket="bucket").put_bytes(_ROUND_TRIP_KEY, b"tampered", metadata=metadata)

    assert client.put_calls == []


def test_put_bytes_maps_client_error_to_upload_error(monkeypatch):
    client = _FakeStorageClient(put_error=_FakeClientError("denied"))
    _install_boto3(monkeypatch, client)

    with pytest.raises(S3UploadError, match="Failed to upload object to s3://bucket/"):
        VaultS3(bucket="bucket").put_bytes(_ROUND_TRIP_KEY, b"data")


def test_get_bytes_reads_streaming_body_and_closes_it(monkeypatch):
    client = _FakeStorageClient(store={_ROUND_TRIP_KEY: b"stored-bytes"})
    _install_boto3(monkeypatch, client)

    result = VaultS3(bucket="bucket").get_bytes(_ROUND_TRIP_KEY)

    assert result == b"stored-bytes"
    assert client.last_body.closed is True


def test_put_then_get_round_trip(monkeypatch):
    client = _FakeStorageClient()
    _install_boto3(monkeypatch, client)

    vault = VaultS3(bucket="bucket")
    payload = b"round-trip-payload"
    vault.put_bytes(_ROUND_TRIP_KEY, payload)

    assert vault.get_bytes(_ROUND_TRIP_KEY) == payload


def test_get_bytes_maps_client_error_to_download_error(monkeypatch):
    client = _FakeStorageClient(get_error=_FakeClientError("missing"))
    _install_boto3(monkeypatch, client)

    with pytest.raises(S3DownloadError, match="Failed to download object from s3://bucket/"):
        VaultS3(bucket="bucket").get_bytes(_ROUND_TRIP_KEY)


def test_put_bytes_missing_boto3_raises_upload_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "boto3", raising=False)
    original_import = __import__

    def _raising_import(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("No module named boto3")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raising_import)

    with pytest.raises(S3UploadError):
        VaultS3(bucket="bucket").put_bytes(_ROUND_TRIP_KEY, b"data")


def test_get_bytes_missing_boto3_raises_download_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "boto3", raising=False)
    original_import = __import__

    def _raising_import(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("No module named boto3")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _raising_import)

    with pytest.raises(S3DownloadError):
        VaultS3(bucket="bucket").get_bytes(_ROUND_TRIP_KEY)
