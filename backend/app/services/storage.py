"""Storage backend selection for evidence/export artifact persistence.

Resolves the active vault implementation from ``settings.STORAGE_BACKEND`` so the
evidence and export pipelines and the export download endpoint all share one
backend decision. The controlled pilot uses the filesystem-backed vault; the S3
vault remains available for the deferred cloud path.

The vault classes are looked up via their modules at call time (rather than
imported into this module's namespace) so existing test patches such as
``patch("app.services.vault_s3.VaultS3")`` continue to intercept construction.
"""

from __future__ import annotations

from typing import Any

from app.services import vault_fs, vault_s3

FILESYSTEM_BACKEND = "filesystem"
S3_BACKEND = "s3"

_FILESYSTEM_ALIASES = frozenset({"filesystem", "fs", "file", "local"})
_S3_ALIASES = frozenset({"s3", "aws", "aws_s3"})


def normalize_storage_backend(value: str | None) -> str:
    """Normalize a configured backend value to ``filesystem`` or ``s3``.

    Accepts the spellings used across env files and settings (``fs``,
    ``filesystem``, ``local``, ``s3``) and raises for anything unsupported so
    misconfiguration fails loudly rather than silently falling back.
    """
    normalized = (value or "").strip().lower()
    if normalized in _FILESYSTEM_ALIASES:
        return FILESYSTEM_BACKEND
    if normalized in _S3_ALIASES:
        return S3_BACKEND
    raise ValueError(f"Unsupported storage backend: {value!r}")


def is_filesystem_backend(settings: Any) -> bool:
    """Return True when the active storage backend is the filesystem vault."""
    return normalize_storage_backend(settings.STORAGE_BACKEND) == FILESYSTEM_BACKEND


def get_vault(settings: Any) -> Any:
    """Return the vault instance for the active storage backend.

    Both vaults expose the same ``put_bytes``/``get_bytes``/``presign_download``
    interface, so call sites stay uniform regardless of backend.
    """
    if is_filesystem_backend(settings):
        return vault_fs.VaultFilesystem(root=settings.VAULT_ROOT)
    return vault_s3.VaultS3(bucket=settings.S3_BUCKET, region=settings.AWS_REGION)
