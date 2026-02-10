"""Tests for the filesystem-backed vault."""

from pathlib import Path

import pytest

from app.services.vault_fs import VaultFilesystem


def test_put_get_bytes_round_trip(tmp_path):
    vault = VaultFilesystem(str(tmp_path))
    key = "org/org-1/incidents/inc-1/exports/test.zip"
    payload = b"vault-bytes"

    stored_path = vault.put_bytes(key, payload)

    assert Path(stored_path).read_bytes() == payload
    assert vault.get_bytes(key) == payload


@pytest.mark.parametrize(
    "key",
    [
        "../secrets.txt",
        "/etc/passwd",
        "org/../secrets.txt",
        "org/foo/../secrets.txt",
        "org\\secrets.txt",
    ],
)
def test_rejects_path_traversal(tmp_path, key):
    vault = VaultFilesystem(str(tmp_path))

    with pytest.raises(ValueError):
        vault.put_bytes(key, b"nope")


def test_presign_download_returns_file_uri(tmp_path):
    vault = VaultFilesystem(str(tmp_path))
    key = "org/org-1/incidents/inc-1/artifacts/blob.bin"
    vault.put_bytes(key, b"data")

    url = vault.presign_download(key)

    assert url.startswith("file://")
