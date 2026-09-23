import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import lru_cache

from mcp_gateway.config.gateway import get_gateway_settings
from mcp_gateway.config.rate_limit import RateLimitConfig
from mcp_gateway.middleware.errors import RateLimitExceededError


class RateLimiter(ABC):
    """Enforces a per-key request rate.

    Isolated behind this interface so the storage backend can be swapped for
    a distributed one (e.g. Redis, shared across gateway instances) without
    changing any call site. `InMemoryRateLimiter` is the single-process
    implementation used for the gateway's first version.
    """

    @abstractmethod
    async def check(self, key: str) -> None:
        """Raise `RateLimitExceededError` if `key` has exceeded its limit."""
        raise NotImplementedError


class NoOpRateLimiter(RateLimiter):
    """Always allows requests. Used when rate limiting is disabled."""

    async def check(self, key: str) -> None:
        return None


class InMemoryRateLimiter(RateLimiter):
    """Single-process token-bucket rate limiter, keyed per client.

    Each key gets its own bucket of `burst` tokens (default: `requests_per_minute`)
    that refills continuously at `requests_per_minute / 60` tokens per second.
    A single lock serializes bucket updates; adequate for one process, but a
    horizontally-scaled deployment needs a shared-storage `RateLimiter`
    instead of running one of these per instance.
    """

    def __init__(
        self,
        requests_per_minute: int,
        burst: int | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate_per_second = requests_per_minute / 60.0
        self._capacity = float(burst if burst is not None else requests_per_minute)
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        async with self._lock:
            now = self._clock()
            tokens, last_refill = self._buckets.get(key, (self._capacity, now))
            elapsed = max(0.0, now - last_refill)
            tokens = min(self._capacity, tokens + elapsed * self._rate_per_second)

            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return

            self._buckets[key] = (tokens, now)
            retry_after = (1.0 - tokens) / self._rate_per_second
            raise RateLimitExceededError(key, retry_after)


def build_rate_limiter(config: RateLimitConfig) -> RateLimiter:
    if not config.enabled:
        return NoOpRateLimiter()
    return InMemoryRateLimiter(config.requests_per_minute, config.burst)


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """Return the process-wide rate limiter, built once from gateway settings."""
    return build_rate_limiter(get_gateway_settings().rate_limit)
