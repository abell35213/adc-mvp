"""ZIP packaging + integrity helpers for exports."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from typing import Any


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_checksums_sha256(files: dict[str, bytes], package_root: str) -> bytes:
    lines: list[str] = []
    for path in sorted(files.keys()):
        rel = path.removeprefix(f"{package_root}/")
        lines.append(f"{hash_bytes(files[path])}  {rel}")
    return ("\n".join(lines) + "\n").encode()


def build_export_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(files.keys()):
            zf.writestr(path, files[path])
    return buf.getvalue()


def build_package_integrity(*, package_sha256: str, file_count: int) -> dict[str, Any]:
    return {
        "package_sha256": package_sha256,
        "file_count": file_count,
        "verification_instructions": [
            "Use sha256sum -c integrity/checksums.sha256 from the package root.",
            "Compare the ZIP SHA-256 with the persisted export record value.",
        ],
    }


def to_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, default=str).encode()
