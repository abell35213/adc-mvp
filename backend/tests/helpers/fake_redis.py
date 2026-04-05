"""Test doubles for Redis-backed rate limiting."""

import threading
import time


class FakeRedisRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._zsets: dict[str, list[tuple[int, str]]] = {}
        self._seq: dict[str, int] = {}
        self._expires_at: dict[str, float] = {}

    def script_load(self, _script: str) -> str:
        return "fake-rate-limit-script"

    def evalsha(self, _sha: str, numkeys: int, redis_key: str, *args):
        assert numkeys == 1
        now_ms = int(args[0])
        window_ms = int(args[1])
        max_calls = int(args[2])
        with self._lock:
            self._purge_expired()
            calls = [
                (score, member)
                for score, member in self._zsets.get(redis_key, [])
                if score > now_ms - window_ms
            ]
            self._zsets[redis_key] = calls
            if len(calls) >= max_calls:
                retry_after = max(1, ((calls[0][0] + window_ms - now_ms + 999) // 1000))
                return [0, retry_after]

            seq_key = f"{redis_key}:seq"
            seq = self._seq.get(seq_key, 0) + 1
            self._seq[seq_key] = seq
            calls.append((now_ms, f"{now_ms}-{seq}"))
            self._zsets[redis_key] = calls
            ttl_seconds = (window_ms + 999) // 1000
            expires_at = time.time() + ttl_seconds
            self._expires_at[redis_key] = expires_at
            self._expires_at[seq_key] = expires_at
            return [1, 0]

    def _purge_expired(self):
        now = time.time()
        for key, expires_at in list(self._expires_at.items()):
            if expires_at <= now:
                self._expires_at.pop(key, None)
                self._zsets.pop(key, None)
                self._seq.pop(key, None)
