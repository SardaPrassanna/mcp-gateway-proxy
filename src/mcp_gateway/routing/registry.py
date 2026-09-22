from collections.abc import Iterable, Iterator

from mcp_gateway.config.gateway import GatewaySettings
from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.routing.errors import UnknownUpstreamError


class UpstreamRegistry:
    """The authoritative set of upstream MCP servers the gateway may forward to.

    Built once from configuration. Clients select an upstream by its stable
    identifier; there is no way to address an upstream that was not explicitly
    configured, which prevents arbitrary/client-supplied forwarding targets.
    """

    def __init__(self, upstreams: Iterable[UpstreamServerConfig]) -> None:
        by_name: dict[str, UpstreamServerConfig] = {}
        for upstream in upstreams:
            if upstream.name in by_name:
                raise ValueError(f"duplicate upstream name registered: {upstream.name!r}")
            by_name[upstream.name] = upstream
        self._by_name = by_name

    @classmethod
    def from_settings(cls, settings: GatewaySettings) -> "UpstreamRegistry":
        return cls(settings.upstreams)

    def get(self, upstream_id: str) -> UpstreamServerConfig:
        """Return the routable upstream for `upstream_id`.

        A disabled upstream is treated identically to an unconfigured one:
        callers cannot distinguish "unknown" from "disabled", which avoids
        leaking the existence of upstreams that are not currently routable.
        """
        upstream = self._by_name.get(upstream_id)
        if upstream is None or not upstream.enabled:
            raise UnknownUpstreamError(upstream_id)
        return upstream

    def __contains__(self, upstream_id: str) -> bool:
        upstream = self._by_name.get(upstream_id)
        return upstream is not None and upstream.enabled

    def __iter__(self) -> Iterator[UpstreamServerConfig]:
        return iter(self._by_name.values())

    def __len__(self) -> int:
        return len(self._by_name)

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(self._by_name)
