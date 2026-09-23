"""The correlation ID: a single identifier for one request, from client to upstream and back."""

import uuid
from collections.abc import Mapping

CORRELATION_ID_HEADER = "X-Request-ID"


def get_or_create_correlation_id(headers: Mapping[str, str]) -> str:
    """Reuse a client-supplied correlation id, or mint a fresh one.

    Letting the client set the header (rather than always generating one)
    lets a correlation id follow a request across a caller's own upstream
    systems, into the gateway, and out to the configured MCP upstream.
    """
    return headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
