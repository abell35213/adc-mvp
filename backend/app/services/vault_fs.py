"""Filesystem-backed vault storage with safe, atomic writes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath


class VaultFilesystem:
    """Stores artifacts on a local filesystem root."""

    def __init__(self, root: str):
        self.root = Path(root)

    def _safe_path(self, key: str) -> Path:
        if "\\" in key:
            raise ValueError("Key contains invalid path separator")
        posix_key = PurePosixPath(key)
        if posix_key.is_absolute():
            raise ValueError("Key must be a relative path")
        if not posix_key.parts or any(part in {"", ".", ".."} for part in posix_key.parts):
            raise ValueError("Key contains invalid path segments")
        target = self.root.joinpath(*posix_key.parts)
        root_resolved = self.root.resolve(strict=False)
        target_resolved = target.resolve(strict=False)
        if root_resolved != target_resolved and root_resolved not in target_resolved.parents:
            raise ValueError("Resolved path escapes vault root")
        return target

    def put_bytes(self, key: str, data: bytes) -> str:
        """Write bytes atomically to the vault and return the file path."""
        target = self._safe_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_handle = None
        try:
            tmp_handle = tempfile.NamedTemporaryFile(
                dir=target.parent,
                prefix=".vault_tmp_",
                delete=False,
            )
            with tmp_handle:
                tmp_handle.write(data)
                tmp_handle.flush()
                os.fsync(tmp_handle.fileno())
            os.replace(tmp_handle.name, target)
        finally:
            if tmp_handle is not None and os.path.exists(tmp_handle.name):
                os.unlink(tmp_handle.name)
        return str(target)

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from the vault."""
        target = self._safe_path(key)
        return target.read_bytes()

    def presign_download(self, key: str, expires_in: int = 3600) -> str:
        """Return a local file URL for the stored object."""
        _ = expires_in
        target = self._safe_path(key)
        return target.resolve(strict=False).as_uri()
