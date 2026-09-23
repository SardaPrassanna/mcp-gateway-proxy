import json
import logging
import math
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from mcp_gateway.auth.authenticator import ApiKeyAuthenticator, get_authenticator
from mcp_gateway.auth.errors import AuthenticationError
from mcp_gateway.config.settings import get_application_settings
from mcp_gateway.middleware.errors import RateLimitExceededError
from mcp_gateway.middleware.rate_limiter import RateLimiter, get_rate_limiter
from mcp_gateway.proxy.errors import UpstreamConnectionError, UpstreamTimeoutError
from mcp_gateway.proxy.http_proxy import CORRELATION_ID_HEADER, MCPHttpProxy
from mcp_gateway.routing.errors import UnknownUpstreamError
from mcp_gateway.routing.router import Router, get_router

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


def get_mcp_http_proxy(request: Request) -> MCPHttpProxy:
    client: httpx.AsyncClient = request.app.state.http_client
    return MCPHttpProxy(client)


def _error_response(
    status_code: int, correlation_id: str, error: str, **extra: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, **extra},
        headers={CORRELATION_ID_HEADER: correlation_id},
    )


@router.api_route("/mcp/{upstream_id}", methods=["GET", "POST", "DELETE"], response_model=None)
async def proxy_mcp_request(
    upstream_id: str,
    request: Request,
    mcp_router: Annotated[Router, Depends(get_router)],
    proxy: Annotated[MCPHttpProxy, Depends(get_mcp_http_proxy)],
    authenticator: Annotated[ApiKeyAuthenticator, Depends(get_authenticator)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> JSONResponse | StreamingResponse:
    correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())

    try:
        principal = authenticator.authenticate(request.headers.get(authenticator.header_name))
    except AuthenticationError:
        logger.info("rejected unauthenticated request: correlation_id=%s", correlation_id)
        return _error_response(401, correlation_id, "unauthorized")

    try:
        await rate_limiter.check(principal.client_id)
    except RateLimitExceededError as exc:
        retry_after = max(1, math.ceil(exc.retry_after_seconds))
        logger.info(
            "rejected request: client=%s exceeded rate limit correlation_id=%s",
            principal.client_id,
            correlation_id,
        )
        response = _error_response(429, correlation_id, "rate limit exceeded")
        response.headers["Retry-After"] = str(retry_after)
        return response

    try:
        upstream = mcp_router.resolve(upstream_id)
    except UnknownUpstreamError:
        logger.info(
            "rejected request for unknown upstream: upstream_id=%s correlation_id=%s",
            upstream_id,
            correlation_id,
        )
        return _error_response(404, correlation_id, "unknown upstream", upstream_id=upstream_id)

    if not principal.can_access(upstream.name):
        logger.info(
            "rejected request: client=%s not authorized for upstream=%s correlation_id=%s",
            principal.client_id,
            upstream.name,
            correlation_id,
        )
        return _error_response(403, correlation_id, "forbidden", upstream_id=upstream_id)

    body = await request.body()

    if request.method == "POST" and body:
        try:
            json.loads(body)
        except json.JSONDecodeError:
            logger.info(
                "rejected malformed request body: upstream=%s correlation_id=%s",
                upstream.name,
                correlation_id,
            )
            return _error_response(
                400, correlation_id, "malformed request: body must be valid JSON"
            )

    settings = get_application_settings()
    timeout_seconds = upstream.timeout_seconds or settings.request_timeout_seconds

    try:
        upstream_response = await proxy.forward(
            upstream,
            method=request.method,
            headers=request.headers,
            content=body,
            timeout_seconds=timeout_seconds,
            correlation_id=correlation_id,
        )
    except UpstreamTimeoutError:
        return _error_response(504, correlation_id, "upstream timed out", upstream=upstream.name)
    except UpstreamConnectionError:
        return _error_response(
            502, correlation_id, "failed to reach upstream", upstream=upstream.name
        )

    logger.info(
        "forwarded request: upstream=%s method=%s status=%s correlation_id=%s",
        upstream.name,
        request.method,
        upstream_response.status_code,
        correlation_id,
    )
    return StreamingResponse(
        upstream_response.body,
        status_code=upstream_response.status_code,
        headers=upstream_response.headers,
    )
