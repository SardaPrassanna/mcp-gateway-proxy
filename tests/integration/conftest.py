import json
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping, Sequence
from typing import Any

import httpx
import pytest_asyncio

from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.main import create_app
from mcp_gateway.routing.registry import UpstreamRegistry
from mcp_gateway.routing.router import StaticRouter, get_router

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
GatewayFactory = Callable[
    [Sequence[UpstreamServerConfig], httpx.AsyncBaseTransport], Awaitable[httpx.AsyncClient]
]


async def json_echo_upstream(scope: Scope, receive: Receive, send: Send) -> None:
    """A minimal ASGI upstream that echoes the request body and the correlation id it received."""
    assert scope["type"] == "http"
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break

    headers = {key.decode().lower(): value.decode() for key, value in scope["headers"]}
    payload = json.loads(body) if body else None
    response_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "result": {"echo": payload},
            "received_correlation_id": headers.get("x-request-id"),
        }
    ).encode()

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": response_body})


def status_code_upstream(status: int) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    """An ASGI upstream that always responds `status` with an empty JSON body."""

    async def _app(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})

    return _app


def raising_transport(make_exc: Callable[[httpx.Request], Exception]) -> httpx.MockTransport:
    """A transport whose every request raises the exception `make_exc` builds for it.

    Used to simulate network-level failures (connection refused, timeout) without
    depending on real sockets or a real MCP server.
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        raise make_exc(request)

    return httpx.MockTransport(_handler)


class RecordingTransport(httpx.MockTransport):
    """A transport that records every request it receives and returns a fixed response.

    Lets a test assert exactly what left the gateway (URL, headers) rather than
    only what came back, which is what proves the gateway never honors a
    client-supplied forwarding target.
    """

    def __init__(
        self,
        status_code: int = 200,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.requests: list[httpx.Request] = []
        body = json.dumps(json_body if json_body is not None else {"jsonrpc": "2.0", "result": {}})

        def _handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(
                status_code,
                content=body.encode(),
                headers={"content-type": "application/json", **(headers or {})},
            )

        super().__init__(_handler)


def multi_route_transport(routes: dict[str, httpx.Response]) -> httpx.MockTransport:
    """A transport that dispatches by request path, simulating several distinct upstreams."""

    def _handler(request: httpx.Request) -> httpx.Response:
        response = routes.get(request.url.path)
        if response is None:
            return httpx.Response(404, json={"error": "no route configured for test"})
        return response

    return httpx.MockTransport(_handler)


@pytest_asyncio.fixture
async def gateway_factory() -> AsyncIterator[GatewayFactory]:
    clients: list[httpx.AsyncClient] = []

    async def _create(
        upstreams: Sequence[UpstreamServerConfig],
        upstream_transport: httpx.AsyncBaseTransport,
    ) -> httpx.AsyncClient:
        app = create_app()
        app.dependency_overrides[get_router] = lambda: StaticRouter(UpstreamRegistry(upstreams))

        upstream_client = httpx.AsyncClient(transport=upstream_transport)
        app.state.http_client = upstream_client
        clients.append(upstream_client)

        gateway_client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://gateway.test"
        )
        clients.append(gateway_client)
        return gateway_client

    yield _create

    for client in clients:
        await client.aclose()
