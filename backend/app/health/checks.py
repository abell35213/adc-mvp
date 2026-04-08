"""Dependency checks used by health endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import redis
from sqlalchemy import text

from app.api.routes_driver_auth import _get_redis_client
from app.core.config import settings
from app.db.session import engine


@dataclass(slots=True)
class CheckResult:
    """Normalized health check result payload."""

    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "detail": self.detail}


def check_database() -> CheckResult:
    """Validate that the database can accept simple queries."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return CheckResult(ok=True, detail="reachable")
    except Exception as exc:  # pragma: no cover - defensive guard
        return CheckResult(ok=False, detail=f"{type(exc).__name__}: {exc}")


def check_redis() -> CheckResult:
    """Validate Redis availability used by driver OTP rate limiting."""

    try:
        client = _get_redis_client()
        if client.ping():
            return CheckResult(ok=True, detail="reachable")
        return CheckResult(ok=False, detail="ping returned false")
    except (redis.RedisError, OSError) as exc:
        return CheckResult(ok=False, detail=f"{type(exc).__name__}: {exc}")


def check_storage(deep: bool = False) -> CheckResult:
    """Optional storage deep check for debugging readiness issues."""

    if not deep:
        return CheckResult(ok=True, detail="skipped")

    backend = settings.STORAGE_BACKEND.strip().lower()
    if backend == "filesystem":
        root = Path(settings.VAULT_ROOT)
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".healthcheck"
            probe.write_bytes(b"ok")
            probe.unlink(missing_ok=True)
            return CheckResult(ok=True, detail="filesystem writable")
        except OSError as exc:
            return CheckResult(ok=False, detail=f"{type(exc).__name__}: {exc}")

    if backend == "s3":
        if not settings.S3_ARTIFACTS_BUCKET.strip() or not settings.S3_EXPORTS_BUCKET.strip():
            return CheckResult(ok=False, detail="missing required S3 bucket configuration")
        return CheckResult(ok=True, detail="s3 buckets configured")

    return CheckResult(ok=False, detail=f"unsupported storage backend: {backend}")
