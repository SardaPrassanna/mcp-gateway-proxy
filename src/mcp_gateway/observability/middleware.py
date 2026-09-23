"""ASGI middleware that assigns a correlation id to every request and logs its outcome."""

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from mcp_gateway.observability.correlation import (
    CORRELATION_ID_HEADER,
    get_or_create_correlation_id,
)

logger = logging.getLogger("mcp_gateway.access")

Endpoint = Callable[[Request], Awaitable[Response]]


async def access_log_middleware(request: Request, call_next: Endpoint) -> Response:
    correlation_id = get_or_create_correlation_id(request.headers)
    request.state.correlation_id = correlation_id

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)

    response.headers[CORRELATION_ID_HEADER] = correlation_id
    logger.info(
        "request completed",
        extra={
            "event": "request_completed",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
