"""Redis-backed rate limiting helpers for API boundaries."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, cast

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max_calls = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local current = redis.call('ZCARD', key)
if current >= max_calls then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if oldest[2] then
        retry_after = math.ceil((tonumber(oldest[2]) + window_ms - now_ms) / 1000)
        if retry_after < 1 then
            retry_after = 1
        end
    end
    return {0, retry_after}
end

local request_id = tostring(now_ms) .. '-' .. tostring(redis.call('INCR', key .. ':seq'))
redis.call('ZADD', key, now_ms, request_id)
local ttl_seconds = math.ceil(window_ms / 1000)
redis.call('EXPIRE', key, ttl_seconds)
redis.call('EXPIRE', key .. ':seq', ttl_seconds)
return {1, 0}
"""

_rate_limit_script_sha: Any = None
_redis_client: redis.Redis | None = None


def _get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_client


def _subject_hash(subject: str) -> str:
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        subject.encode(),
        hashlib.sha256,
    ).hexdigest()


def _redis_key(*, bucket_name: str, subject: str, window_seconds: int) -> str:
    return f"ratelimit:{bucket_name}:{_subject_hash(subject)}:{window_seconds}s"


def _run_rate_limit_script(redis_client: redis.Redis, redis_key: str, max_calls: int, window_seconds: int):
    global _rate_limit_script_sha
    now_ms = int(time.time() * 1000)
    window_ms = window_seconds * 1000
    args = [now_ms, window_ms, max_calls]
    if _rate_limit_script_sha is None:
        _rate_limit_script_sha = redis_client.script_load(_RATE_LIMIT_SCRIPT)
    try:
        return redis_client.evalsha(cast(str, _rate_limit_script_sha), 1, redis_key, *args)
    except redis.exceptions.NoScriptError:
        _rate_limit_script_sha = redis_client.script_load(_RATE_LIMIT_SCRIPT)
        return redis_client.evalsha(cast(str, _rate_limit_script_sha), 1, redis_key, *args)


def _request_identity(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    client = request.client.host if request.client else "unknown"
    return client or "unknown"


def enforce_rate_limit(
    request: Request,
    *,
    bucket_name: str,
    subject: str | None,
    max_calls: int,
    window_seconds: int,
    detail: str,
) -> None:
    """Enforce a per-subject + per-client-IP rate limit."""
    if max_calls <= 0:
        return

    identity = subject.strip() if subject else _request_identity(request)
    key = _redis_key(bucket_name=bucket_name, subject=identity, window_seconds=window_seconds)

    try:
        redis_client = _get_redis_client()
        allowed, retry_after = _run_rate_limit_script(redis_client, key, max_calls, window_seconds)
    except (redis.RedisError, OSError) as exc:
        logger.warning("Rate-limit backend unavailable for bucket=%s: %s", bucket_name, exc)
        return

    if int(allowed) == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(int(retry_after))},
        )
