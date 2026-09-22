import httpx

from mcp_gateway.config.upstream import UpstreamServerConfig
from tests.integration.conftest import GatewayFactory, json_echo_upstream, raising_transport


async def test_forwards_request_to_configured_upstream(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    client = await gateway_factory([upstream], httpx.ASGITransport(app=json_echo_upstream))

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0", "method": "ping"})

    assert response.status_code == 200
    assert response.json()["result"]["echo"] == {"jsonrpc": "2.0", "method": "ping"}


async def test_unknown_upstream_is_rejected(gateway_factory: GatewayFactory) -> None:
    client = await gateway_factory([], httpx.ASGITransport(app=json_echo_upstream))

    response = await client.post("/mcp/does-not-exist", json={"jsonrpc": "2.0"})

    assert response.status_code == 404
    assert response.json()["upstream_id"] == "does-not-exist"


async def test_malformed_request_body_is_rejected(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    client = await gateway_factory([upstream], httpx.ASGITransport(app=json_echo_upstream))

    response = await client.post("/mcp/svc-a", content=b"not json")

    assert response.status_code == 400


async def test_upstream_connection_failure_returns_502(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = raising_transport(lambda req: httpx.ConnectError("refused", request=req))
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 502


async def test_upstream_timeout_returns_504(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = raising_transport(lambda req: httpx.ReadTimeout("timed out", request=req))
    client = await gateway_factory([upstream], transport)

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert response.status_code == 504


async def test_correlation_id_is_generated_and_returned(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    client = await gateway_factory([upstream], httpx.ASGITransport(app=json_echo_upstream))

    response = await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"})

    assert "x-request-id" in response.headers
    assert response.json()["received_correlation_id"] == response.headers["x-request-id"]


async def test_client_supplied_correlation_id_is_preserved(gateway_factory: GatewayFactory) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    client = await gateway_factory([upstream], httpx.ASGITransport(app=json_echo_upstream))

    response = await client.post(
        "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-Request-ID": "client-supplied-id"}
    )

    assert response.headers["x-request-id"] == "client-supplied-id"
    assert response.json()["received_correlation_id"] == "client-supplied-id"
