from abc import ABC, abstractmethod
from functools import lru_cache

from mcp_gateway.config.gateway import get_gateway_settings
from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.routing.registry import UpstreamRegistry


class Router(ABC):
    """Resolves an upstream identifier to a configured upstream server.

    Transport-agnostic by design: implementations must not depend on FastAPI
    or any HTTP framework, so routing strategy can evolve (e.g. weighted or
    health-aware selection) without changes to the HTTP layer or the proxy.
    """

    @abstractmethod
    def resolve(self, upstream_id: str) -> UpstreamServerConfig:
        """Return the configured upstream for `upstream_id`.

        Raises `UnknownUpstreamError` if no such upstream is configured.
        """
        raise NotImplementedError


class StaticRouter(Router):
    """Routes strictly by exact, configured upstream identifier."""

    def __init__(self, registry: UpstreamRegistry) -> None:
        self._registry = registry

    def resolve(self, upstream_id: str) -> UpstreamServerConfig:
        return self._registry.get(upstream_id)


@lru_cache
def get_router() -> Router:
    """Return the process-wide router, built once from gateway settings."""
    registry = UpstreamRegistry.from_settings(get_gateway_settings())
    return StaticRouter(registry)
