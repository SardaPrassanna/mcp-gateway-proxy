"""Resilience coverage for Phase 11: timeout enforcement, bounded upstream
failures, and rate-limit window behavior under a fake clock.

All scenarios are deterministic: upstream latency and failures are simulated
through mock transports, never real sleeps.
"""

import time

import httpx

from mcp_gateway.config.settings import get_application_settings
from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.middleware.rate_limiter import InMemoryRateLimiter, get_rate_limiter
from tests.integration.conftest import GatewayFactory, RecordingTransport, raising_transport


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def test_configured_upstream_timeout_is_forwarded_to_upstream_request(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(
        name="svc-a", url="http://fake-upstream.test/mcp", timeout_seconds=2.0
    )
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert transport.requests[0].extensions["timeout"]["read"] == 2.0


async def test_global_timeout_used_when_upstream_has_no_override(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    expected = get_application_settings().request_timeout_seconds
    assert transport.requests[0].extensions["timeout"]["read"] == expected


async def test_slow_upstream_does_not_block_gateway_indefinitely(
    gateway_factory: GatewayFactory,
) -> None:
    """A hung upstream must be bounded by the configured timeout, not left to
    block the gateway forever. Simulated deterministically via a transport
    that raises `ReadTimeout` instead of a real sleep past a deadline."""
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = raising_transport(lambda req: httpx.ReadTimeout("stalled", request=req))
    client = await gateway_factory([upstream], transport)

    started = time.monotonic()
    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
    elapsed = time.monotonic() - started

    assert response.status_code == 504
    assert elapsed < 1.0  # gateway returned promptly instead of hanging


async def test_upstream_connection_failure_is_controlled_and_does_not_leak_internals(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = raising_transport(lambda req: httpx.ConnectError("refused", request=req))
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 502
    body = response.json()
    assert body == {"error": "failed to reach upstream", "upstream": "svc-a"}
    assert "ConnectError" not in response.text
    assert "Traceback" not in response.text


async def test_rate_limit_window_resets_after_refill_period(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    clock = FakeClock()
    limiter = InMemoryRateLimiter(requests_per_minute=60, burst=1, clock=clock)
    client = await gateway_factory(
        [upstream], transport, dependency_overrides={get_rate_limiter: lambda: limiter}
    )

    first = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
    blocked = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    clock.advance(1.0)  # one token/sec refill rate -> bucket is full again
    recovered = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert first.status_code == 200
    assert blocked.status_code == 429
    assert recovered.status_code == 200
