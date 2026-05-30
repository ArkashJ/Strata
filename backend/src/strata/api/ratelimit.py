"""Token-bucket rate limiting (Wave 3 / AC3.2).

Per-key (per-``org_id``) token bucket on the LLM/compute routes: ``rate_limit_rpm``
tokens, refilled continuously. Exceeding the bucket is a 429 with a ``Retry-After``
header. In-process (single container) with a clean seam for a Redis-backed store.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException

from ..config import settings


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self, rpm: int, now_fn: Callable[[], float] = time.monotonic) -> None:
        self.capacity = float(rpm)
        self.refill_per_sec = rpm / 60.0
        self._now = now_fn
        self._buckets: dict[str, _Bucket] = {}

    def _refill(self, b: _Bucket, now: float) -> None:
        elapsed = max(0.0, now - b.updated)
        b.tokens = min(self.capacity, b.tokens + elapsed * self.refill_per_sec)
        b.updated = now

    def check(self, key: str) -> tuple[bool, float]:
        """Consume one token. Returns (allowed, retry_after_seconds)."""
        now = self._now()
        b = self._buckets.get(key)
        if b is None:
            b = _Bucket(tokens=self.capacity, updated=now)
            self._buckets[key] = b
        self._refill(b, now)
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True, 0.0
        retry_after = (1.0 - b.tokens) / self.refill_per_sec if self.refill_per_sec > 0 else 60.0
        return False, retry_after

    def reset(self) -> None:
        self._buckets.clear()


# Module singleton sized from config.
_limiter = RateLimiter(settings.rate_limit_rpm)


def get_limiter() -> RateLimiter:
    return _limiter


def enforce_rate_limit(org_id: str) -> None:
    """Raise 429 (+ Retry-After) when the org's bucket is empty."""
    allowed, retry_after = _limiter.check(org_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(max(1, int(retry_after + 0.999)))},
        )
