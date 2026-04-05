"""Redis-backed OTP rate-limiting behavior tests."""

from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
import pytest

from app.api import routes_driver_auth
from tests.helpers.fake_redis import FakeRedisRateLimiter


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    routes_driver_auth._redis_client = None
    routes_driver_auth._rate_limit_script_sha = None
    yield
    routes_driver_auth._redis_client = None
    routes_driver_auth._rate_limit_script_sha = None


def test_rate_limit_blocks_concurrent_requests():
    fake_redis = FakeRedisRateLimiter()
    routes_driver_auth._redis_client = fake_redis
    routes_driver_auth._rate_limit_script_sha = None
    phone = "+15550001234"

    def _attempt():
        try:
            routes_driver_auth._enforce_rate_limit(
                "request",
                phone,
                routes_driver_auth._REQUEST_LIMIT,
            )
            return True
        except HTTPException:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _i: _attempt(), range(12)))

    assert sum(results) == routes_driver_auth._REQUEST_LIMIT


def test_rate_limit_state_shared_across_instances():
    shared_fake_redis = FakeRedisRateLimiter()
    phone = "+15559990000"

    routes_driver_auth._redis_client = shared_fake_redis
    routes_driver_auth._rate_limit_script_sha = None
    for _ in range(routes_driver_auth._REQUEST_LIMIT - 1):
        routes_driver_auth._enforce_rate_limit(
            "request",
            phone,
            routes_driver_auth._REQUEST_LIMIT,
        )

    routes_driver_auth._redis_client = shared_fake_redis
    routes_driver_auth._rate_limit_script_sha = None
    routes_driver_auth._enforce_rate_limit(
        "request",
        phone,
        routes_driver_auth._REQUEST_LIMIT,
    )

    blocked = False
    try:
        routes_driver_auth._enforce_rate_limit(
            "request",
            phone,
            routes_driver_auth._REQUEST_LIMIT,
        )
    except HTTPException:
        blocked = True

    assert blocked is True
