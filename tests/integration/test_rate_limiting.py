"""End-to-end coverage for per-client rate limiting (Phase 10)."""

from typing import Any

from mcp_gateway.auth.authenticator import ApiKeyAuthenticator, get_authenticator
from mcp_gateway.config.auth import AuthClient, AuthConfig
from mcp_gateway.config.rate_limit import RateLimitConfig
from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.middleware.rate_limiter import build_rate_limiter, get_rate_limiter
from tests.integration.conftest import DependencyOverrides, GatewayFactory, RecordingTransport


def _rate_limit_override(config: RateLimitConfig) -> DependencyOverrides:
    limiter = build_rate_limiter(config)
    return {get_rate_limiter: lambda: limiter}


async def test_requests_within_limit_are_forwarded(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    config = RateLimitConfig(enabled=True, requests_per_minute=2)
    client = await gateway_factory(
        [upstream], transport, dependency_overrides=_rate_limit_override(config)
    )

    first = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
    second = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(transport.requests) == 2


async def test_request_beyond_limit_is_rejected_with_429(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    config = RateLimitConfig(enabled=True, requests_per_minute=1)
    client = await gateway_factory(
        [upstream], transport, dependency_overrides=_rate_limit_override(config)
    )

    await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
    blocked = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert len(transport.requests) == 1


async def test_rate_limit_disabled_by_default_allows_many_requests(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    for _ in range(10):
        response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
        assert response.status_code == 200

    assert len(transport.requests) == 10


async def test_rate_limit_is_isolated_per_client(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[
            AuthClient(client_id="client-a", api_key="key-a"),
            AuthClient(client_id="client-b", api_key="key-b"),
        ],
    )
    config = RateLimitConfig(enabled=True, requests_per_minute=1)
    overrides: dict[Any, Any] = {
        get_authenticator: lambda: ApiKeyAuthenticator(auth),
        **_rate_limit_override(config),
    }
    client = await gateway_factory([upstream], transport, dependency_overrides=overrides)

    a_first = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )
    a_second = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )
    b_first = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-b"}
    )

    assert a_first.status_code == 200
    assert a_second.status_code == 429
    assert b_first.status_code == 200  # client-b's bucket is unaffected by client-a


async def test_rate_limited_response_carries_correlation_id(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    config = RateLimitConfig(enabled=True, requests_per_minute=1)
    client = await gateway_factory(
        [upstream], transport, dependency_overrides=_rate_limit_override(config)
    )

    await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-Request-ID": "req-1"})
    blocked = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-Request-ID": "req-2"}
    )

    assert blocked.headers["X-Request-ID"] == "req-2"
