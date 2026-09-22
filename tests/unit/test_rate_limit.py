import pytest
from pydantic import ValidationError

from mcp_gateway.config.rate_limit import RateLimitConfig


def test_rate_limit_defaults_to_disabled() -> None:
    rate_limit = RateLimitConfig()

    assert rate_limit.enabled is False
    assert rate_limit.requests_per_minute == 60
    assert rate_limit.burst is None


def test_rate_limit_rejects_non_positive_requests_per_minute() -> None:
    with pytest.raises(ValidationError):
        RateLimitConfig(requests_per_minute=0)


def test_rate_limit_rejects_burst_below_requests_per_minute() -> None:
    with pytest.raises(ValidationError):
        RateLimitConfig(requests_per_minute=60, burst=10)


def test_rate_limit_accepts_burst_at_or_above_requests_per_minute() -> None:
    rate_limit = RateLimitConfig(requests_per_minute=60, burst=120)

    assert rate_limit.burst == 120
