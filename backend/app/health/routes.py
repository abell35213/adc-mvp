"""Health endpoints for liveness/readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.health.checks import check_database, check_redis, check_storage

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> JSONResponse:
    """Compatibility health endpoint returning readiness semantics."""

    return await readiness_check()


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe: process is running."""

    return {"status": "ok"}


@router.get("/ready")
async def readiness_check(
    deep_storage: bool = Query(False, description="Perform optional storage deep check."),
) -> JSONResponse:
    """Kubernetes readiness probe: critical traffic dependencies are healthy."""

    db = check_database()
    redis = check_redis()
    storage = check_storage(deep=deep_storage)

    ready = db.ok and redis.ok and storage.ok
    payload = {
        "status": "ok" if ready else "fail",
        "checks": {
            "database": db.as_dict(),
            "redis": redis.as_dict(),
            "storage": storage.as_dict(),
        },
    }
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload, status_code=status_code)
