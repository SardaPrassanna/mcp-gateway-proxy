"""End-to-end security coverage for the gateway's auth boundary (Phase 9).

Exercises the full request path (ASGI in, upstream transport out) against a
deterministic local mock upstream, from an attacker's perspective: what a
caller without a key, with the wrong key, or with an insufficiently-scoped
key can and cannot reach, and what the gateway ever reveals.
"""

import logging

import pytest

from mcp_gateway.auth.authenticator import ApiKeyAuthenticator, get_authenticator
from mcp_gateway.config.auth import AuthClient, AuthConfig
from mcp_gateway.config.upstream import UpstreamServerConfig
from tests.integration.conftest import DependencyOverrides, GatewayFactory, RecordingTransport

_SECRET_KEY = "sk-live-super-secret-0123456789"


def _auth_override(auth: AuthConfig) -> DependencyOverrides:
    return {get_authenticator: lambda: ApiKeyAuthenticator(auth)}


# --- 1/2/3: missing / invalid / valid API key --------------------------------


async def test_missing_api_key_is_rejected(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 401
    assert transport.requests == []


async def test_invalid_api_key_is_rejected(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "not-the-key"}
    )

    assert response.status_code == 401
    assert transport.requests == []


async def test_valid_api_key_is_accepted(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": _SECRET_KEY}
    )

    assert response.status_code == 200
    assert len(transport.requests) == 1


# --- 4/5: unauthorized / authorized upstream access --------------------------


async def test_unauthorized_upstream_access_is_rejected(gateway_factory: GatewayFactory) -> None:
    database = UpstreamServerConfig(name="database", url="http://fake-upstream.test/db")
    jira = UpstreamServerConfig(name="jira", url="http://fake-upstream.test/jira")
    transport = RecordingTransport()
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"database"})],
    )
    client = await gateway_factory(
        [database, jira], transport, dependency_overrides=_auth_override(auth)
    )

    response = await client.post(
        "/mcp/jira", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )

    assert response.status_code == 403
    assert transport.requests == []


async def test_authorized_upstream_access_is_forwarded(gateway_factory: GatewayFactory) -> None:
    database = UpstreamServerConfig(name="database", url="http://fake-upstream.test/db")
    jira = UpstreamServerConfig(name="jira", url="http://fake-upstream.test/jira")
    transport = RecordingTransport()
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"database"})],
    )
    client = await gateway_factory(
        [database, jira], transport, dependency_overrides=_auth_override(auth)
    )

    response = await client.post(
        "/mcp/database", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )

    assert response.status_code == 200
    assert len(transport.requests) == 1


# --- 6: API key is not exposed in logs/errors/upstream requests -------------


async def test_api_key_never_appears_in_logs_on_success_or_failure(
    gateway_factory: GatewayFactory, caplog: pytest.LogCaptureFixture
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    with caplog.at_level(logging.DEBUG):
        await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": _SECRET_KEY})
        await client.post(
            "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "wrong-guess-key"}
        )

    log_text = caplog.text
    assert _SECRET_KEY not in log_text
    assert "wrong-guess-key" not in log_text


async def test_api_key_never_forwarded_to_upstream(gateway_factory: GatewayFactory) -> None:
    """The client's gateway credential must never leak to the upstream server."""
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": _SECRET_KEY})

    assert len(transport.requests) == 1
    forwarded_headers = transport.requests[0].headers
    assert "x-api-key" not in forwarded_headers
    assert _SECRET_KEY not in str(forwarded_headers)


async def test_api_key_never_appears_in_error_response_body(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "wrong-guess-key"}
    )

    assert _SECRET_KEY not in response.text
    assert "wrong-guess-key" not in response.text


# --- 8: arbitrary upstream URL injection is rejected (authenticated) --------


async def test_authenticated_request_cannot_redirect_via_body_url(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    await client.post(
        "/mcp/svc-a",
        json={"jsonrpc": "2.0", "url": "http://evil.example.com/steal"},
        headers={"X-API-Key": _SECRET_KEY},
    )

    assert len(transport.requests) == 1
    assert str(transport.requests[0].url) == "http://fake-upstream.test/mcp"


async def test_authenticated_request_cannot_redirect_via_upstream_id(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/evil.example.com",
        json={"jsonrpc": "2.0"},
        headers={"X-API-Key": _SECRET_KEY},
    )

    assert response.status_code == 404
    assert transport.requests == []


# --- 9: malformed authentication headers -------------------------------------


async def test_non_ascii_api_key_header_is_rejected_not_500(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    # httpx's Python API refuses a raw non-ASCII `str` header value outright
    # (it insists on ASCII or explicit bytes), but a real client can and does
    # put arbitrary bytes on the wire; simulate that by supplying bytes directly.
    response = await client.post(
        "/mcp/svc-a",
        json={"jsonrpc": "2.0"},
        headers={b"X-API-Key": "clave-ñ-unicode".encode()},
    )

    assert response.status_code == 401
    assert transport.requests == []


async def test_empty_api_key_header_is_rejected(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": ""})

    assert response.status_code == 401
    assert transport.requests == []


async def test_oversized_api_key_header_is_rejected_not_500(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "x" * 8192}
    )

    assert response.status_code == 401
    assert transport.requests == []


# --- 10: authentication does not bypass routing authorization ---------------


async def test_valid_unrestricted_key_cannot_reach_unconfigured_upstream(
    gateway_factory: GatewayFactory,
) -> None:
    """A globally-valid key grants no access beyond the configured registry."""
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key=_SECRET_KEY)
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    response = await client.post(
        "/mcp/not-configured", json={"jsonrpc": "2.0"}, headers={"X-API-Key": _SECRET_KEY}
    )

    assert response.status_code == 404
    assert transport.requests == []


async def test_authentication_success_does_not_grant_denied_upstream_access(
    gateway_factory: GatewayFactory,
) -> None:
    """Passing authentication must not short-circuit the separate authorization check."""
    database = UpstreamServerConfig(name="database", url="http://fake-upstream.test/db")
    jira = UpstreamServerConfig(name="jira", url="http://fake-upstream.test/jira")
    transport = RecordingTransport()
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"database"})],
    )
    client = await gateway_factory(
        [database, jira], transport, dependency_overrides=_auth_override(auth)
    )

    # This key is genuinely valid (authenticates fine) but scoped to "database" only.
    authorized = await client.post(
        "/mcp/database", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )
    forbidden = await client.post(
        "/mcp/jira", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "key-a"}
    )

    assert authorized.status_code == 200
    assert forbidden.status_code == 403
    assert len(transport.requests) == 1
