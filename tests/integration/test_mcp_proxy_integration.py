import httpx

from mcp_gateway.config.upstream import UpstreamServerConfig
from tests.integration.conftest import GatewayFactory, RecordingTransport, multi_route_transport


async def test_upstream_response_status_and_body_returned_unmodified(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport(status_code=201, json_body={"jsonrpc": "2.0", "id": 7})
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0", "method": "ping"})

    assert response.status_code == 201
    assert response.json() == {"jsonrpc": "2.0", "id": 7}
    assert response.headers["content-type"] == "application/json"


async def test_multiple_upstreams_route_independently(gateway_factory: GatewayFactory) -> None:
    upstream_a = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/upstream-a")
    upstream_b = UpstreamServerConfig(name="svc-b", url="http://fake-upstream.test/upstream-b")
    transport = multi_route_transport(
        {
            "/upstream-a": httpx.Response(200, json={"jsonrpc": "2.0", "result": "from-a"}),
            "/upstream-b": httpx.Response(200, json={"jsonrpc": "2.0", "result": "from-b"}),
        }
    )
    client = await gateway_factory([upstream_a, upstream_b], transport)

    response_a = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})
    response_b = await client.post("/mcp/svc-b", json={"jsonrpc": "2.0"})

    assert response_a.json()["result"] == "from-a"
    assert response_b.json()["result"] == "from-b"


async def test_unconfigured_upstream_id_is_never_routable(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/evil.example.com", json={"jsonrpc": "2.0"})

    assert response.status_code == 404
    assert transport.requests == []


async def test_client_supplied_url_in_body_does_not_change_forwarding_target(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    await client.post(
        "/mcp/svc-a",
        json={"jsonrpc": "2.0", "method": "ping", "url": "http://evil.example.com/steal"},
    )

    assert len(transport.requests) == 1
    assert str(transport.requests[0].url) == "http://fake-upstream.test/mcp"


async def test_client_supplied_url_header_is_not_honored(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    client = await gateway_factory([upstream], transport)

    await client.post(
        "/mcp/svc-a",
        json={"jsonrpc": "2.0"},
        headers={"X-Upstream-Url": "http://evil.example.com/steal"},
    )

    assert len(transport.requests) == 1
    forwarded = transport.requests[0]
    assert str(forwarded.url) == "http://fake-upstream.test/mcp"
    assert "x-upstream-url" not in forwarded.headers


async def test_upstream_server_error_is_passed_through(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport(
        status_code=500, json_body={"jsonrpc": "2.0", "error": {"code": -32000, "message": "boom"}}
    )
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "boom"


async def test_upstream_client_error_is_distinct_from_gateway_malformed_request(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport(status_code=400, json_body={"jsonrpc": "2.0", "error": "bad"})
    client = await gateway_factory([upstream], transport)

    # A well-formed request that the upstream itself rejects must surface the
    # upstream's 400, not be conflated with the gateway's own malformed-body check.
    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 400
    assert response.json() == {"jsonrpc": "2.0", "error": "bad"}
    assert len(transport.requests) == 1
