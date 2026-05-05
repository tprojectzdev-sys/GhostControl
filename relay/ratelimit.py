"""In-memory token-bucket rate limiter.

Single-process. Suitable for a single-user relay; not for multi-instance.
Two independent buckets per principal: a general bucket and a 'power' bucket
so destructive commands get a tighter cap.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    capacity: int
    tokens: float
    refill_per_sec: float
    last_refill: float


class RateLimiter:
    def __init__(self, default_per_min: int, power_per_min: int) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._default_per_min = default_per_min
        self._power_per_min = power_per_min

    def _bucket(self, principal: str, kind: str) -> _Bucket:
        key = (principal, kind)
        b = self._buckets.get(key)
        if b is not None:
            return b
        per_min = self._power_per_min if kind == "power" else self._default_per_min
        per_sec = per_min / 60.0
        b = _Bucket(
            capacity=per_min,
            tokens=float(per_min),
            refill_per_sec=per_sec,
            last_refill=time.monotonic(),
        )
        self._buckets[key] = b
        return b

    def allow(self, principal: str, kind: str = "general") -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds). retry_after_seconds is 0 when allowed."""
        with self._lock:
            b = self._bucket(principal, kind)
            now = time.monotonic()
            elapsed = now - b.last_refill
            b.tokens = min(b.capacity, b.tokens + elapsed * b.refill_per_sec)
            b.last_refill = now
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True, 0.0
            need = 1.0 - b.tokens
            return False, need / b.refill_per_sec
