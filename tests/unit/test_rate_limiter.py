import pytest

from mcp_gateway.config.rate_limit import RateLimitConfig
from mcp_gateway.middleware.errors import RateLimitExceededError
from mcp_gateway.middleware.rate_limiter import (
    InMemoryRateLimiter,
    NoOpRateLimiter,
    build_rate_limiter,
)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def test_noop_rate_limiter_always_allows() -> None:
    limiter = NoOpRateLimiter()

    for _ in range(1000):
        await limiter.check("any-client")


async def test_build_rate_limiter_returns_noop_when_disabled() -> None:
    limiter = build_rate_limiter(RateLimitConfig(enabled=False))

    assert isinstance(limiter, NoOpRateLimiter)


async def test_build_rate_limiter_returns_in_memory_when_enabled() -> None:
    limiter = build_rate_limiter(RateLimitConfig(enabled=True, requests_per_minute=60))

    assert isinstance(limiter, InMemoryRateLimiter)


async def test_allows_requests_up_to_capacity() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=3, clock=clock)

    for _ in range(3):
        await limiter.check("client-a")


async def test_rejects_request_once_capacity_is_exhausted() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=3, clock=clock)

    for _ in range(3):
        await limiter.check("client-a")

    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.check("client-a")

    assert exc_info.value.key == "client-a"
    assert exc_info.value.retry_after_seconds > 0


async def test_retry_after_reflects_time_until_next_token() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=60, burst=1, clock=clock)  # 1 token/sec

    await limiter.check("client-a")

    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.check("client-a")

    assert exc_info.value.retry_after_seconds == pytest.approx(1.0, abs=0.01)


async def test_bucket_refills_over_time() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=60, burst=1, clock=clock)  # 1 token/sec

    await limiter.check("client-a")

    with pytest.raises(RateLimitExceededError):
        await limiter.check("client-a")

    clock.advance(1.0)

    await limiter.check("client-a")  # refilled, should succeed


async def test_bucket_never_exceeds_capacity() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=60, burst=1, clock=clock)

    clock.advance(1000.0)  # idle for a long time before first request

    await limiter.check("client-a")
    with pytest.raises(RateLimitExceededError):
        await limiter.check("client-a")


async def test_separate_keys_have_independent_buckets() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=1, clock=clock)

    await limiter.check("client-a")
    with pytest.raises(RateLimitExceededError):
        await limiter.check("client-a")

    await limiter.check("client-b")  # unaffected by client-a's exhausted bucket


async def test_burst_allows_capacity_above_steady_rate() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=10, burst=20, clock=clock)

    for _ in range(20):
        await limiter.check("client-a")

    with pytest.raises(RateLimitExceededError):
        await limiter.check("client-a")
