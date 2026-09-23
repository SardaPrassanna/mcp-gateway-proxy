import logging
from collections.abc import AsyncIterator, Mapping

import httpx
from mcp.server.streamable_http import LAST_EVENT_ID_HEADER, MCP_SESSION_ID_HEADER
from mcp.shared.inbound import MCP_PROTOCOL_VERSION_HEADER

from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.observability.correlation import CORRELATION_ID_HEADER
from mcp_gateway.proxy.errors import UpstreamConnectionError, UpstreamTimeoutError

logger = logging.getLogger(__name__)

# Only headers meaningful to the MCP Streamable HTTP transport are forwarded in
# either direction; nothing else (e.g. Host, Authorization, cookies) crosses the
# gateway boundary implicitly.
_REQUEST_HEADER_ALLOWLIST = frozenset(
    {
        "content-type",
        "accept",
        MCP_SESSION_ID_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
        LAST_EVENT_ID_HEADER,
    }
)
_RESPONSE_HEADER_ALLOWLIST = frozenset({"content-type", MCP_SESSION_ID_HEADER})


class ProxyResponse:
    """The status, headers and streamed body of a forwarded upstream response."""

    __slots__ = ("status_code", "headers", "body")

    def __init__(
        self, status_code: int, headers: dict[str, str], body: AsyncIterator[bytes]
    ) -> None:
        self.status_code = status_code
        self.headers = headers
        self.body = body


def _select_headers(headers: Mapping[str, str], allowlist: frozenset[str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() in allowlist}


async def _stream_body(response: httpx.Response) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()


class MCPHttpProxy:
    """Forwards MCP Streamable HTTP requests to a configured upstream server.

    A pure HTTP transport concern: it knows nothing about how an upstream was
    selected (that is `Router`'s job) or how it was invoked (that is the API
    layer's job), so it can be tested and reused independently of both.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def forward(
        self,
        upstream: UpstreamServerConfig,
        *,
        method: str,
        headers: Mapping[str, str],
        content: bytes,
        timeout_seconds: float,
        correlation_id: str,
    ) -> ProxyResponse:
        forward_headers = _select_headers(headers, _REQUEST_HEADER_ALLOWLIST)
        forward_headers[CORRELATION_ID_HEADER] = correlation_id

        try:
            upstream_request = self._client.build_request(
                method,
                str(upstream.url),
                headers=forward_headers,
                content=content or None,
                timeout=timeout_seconds,
            )
            upstream_response = await self._client.send(upstream_request, stream=True)
        except httpx.TimeoutException as exc:
            logger.warning(
                "upstream timeout: upstream=%s correlation_id=%s", upstream.name, correlation_id
            )
            raise UpstreamTimeoutError(upstream.name) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "upstream connection error: upstream=%s correlation_id=%s error=%s",
                upstream.name,
                correlation_id,
                type(exc).__name__,
            )
            raise UpstreamConnectionError(upstream.name) from exc

        response_headers = _select_headers(
            dict(upstream_response.headers), _RESPONSE_HEADER_ALLOWLIST
        )
        response_headers[CORRELATION_ID_HEADER] = correlation_id

        return ProxyResponse(
            status_code=upstream_response.status_code,
            headers=response_headers,
            body=_stream_body(upstream_response),
        )
