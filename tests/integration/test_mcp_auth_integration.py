from mcp_gateway.auth.authenticator import ApiKeyAuthenticator, get_authenticator
from mcp_gateway.config.auth import AuthClient, AuthConfig
from mcp_gateway.config.upstream import UpstreamServerConfig
from tests.integration.conftest import DependencyOverrides, GatewayFactory, RecordingTransport


def _auth_override(auth: AuthConfig) -> DependencyOverrides:
    return {get_authenticator: lambda: ApiKeyAuthenticator(auth)}


async def test_request_without_api_key_is_rejected_when_auth_enabled(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 401
    assert transport.requests == []


async def test_request_with_wrong_api_key_is_rejected(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "wrong-key"}
    )

    assert response.status_code == 401
    assert transport.requests == []


async def test_request_with_valid_key_and_no_restriction_is_forwarded(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "the-key"}
    )

    assert response.status_code == 200
    assert len(transport.requests) == 1


async def test_client_restricted_to_other_upstream_is_forbidden(
    gateway_factory: GatewayFactory,
) -> None:
    upstream_a = UpstreamServerConfig(name="database", url="http://fake-upstream.test/db")
    upstream_b = UpstreamServerConfig(name="jira", url="http://fake-upstream.test/jira")
    transport = RecordingTransport()
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"database"})],
    )
    client = await gateway_factory(
        [upstream_a, upstream_b], transport, dependency_overrides=_auth_override(auth)
    )

    response = await client.post(
        "/mcp/jira", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )

    assert response.status_code == 403
    assert transport.requests == []


async def test_client_allowed_upstream_is_forwarded(gateway_factory: GatewayFactory) -> None:
    upstream_a = UpstreamServerConfig(name="database", url="http://fake-upstream.test/db")
    upstream_b = UpstreamServerConfig(name="jira", url="http://fake-upstream.test/jira")
    transport = RecordingTransport()
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"database"})],
    )
    client = await gateway_factory(
        [upstream_a, upstream_b], transport, dependency_overrides=_auth_override(auth)
    )

    response = await client.post(
        "/mcp/database", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )

    assert response.status_code == 200
    assert len(transport.requests) == 1


async def test_unauthenticated_request_does_not_leak_unknown_upstream_existence(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    known = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
    unknown = await client.post("/mcp/does-not-exist", json={"jsonrpc": "2.0"})

    # Auth is checked before routing, so both an existing and a nonexistent
    # upstream id are rejected identically without a valid key.
    assert known.status_code == 401
    assert unknown.status_code == 401
    assert transport.requests == []


async def test_disabled_auth_forwards_without_any_key(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 200
