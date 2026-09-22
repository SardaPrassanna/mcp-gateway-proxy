import pytest

from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.routing.errors import UnknownUpstreamError
from mcp_gateway.routing.registry import UpstreamRegistry
from mcp_gateway.routing.router import Router, StaticRouter

_SVC_A = UpstreamServerConfig(name="svc-a", url="http://localhost:9001")


def test_static_router_resolves_configured_upstream() -> None:
    registry = UpstreamRegistry([_SVC_A])
    router = StaticRouter(registry)

    assert router.resolve("svc-a") is _SVC_A


def test_static_router_raises_for_unknown_upstream() -> None:
    registry = UpstreamRegistry([_SVC_A])
    router = StaticRouter(registry)

    with pytest.raises(UnknownUpstreamError):
        router.resolve("does-not-exist")


def test_static_router_never_accepts_arbitrary_urls() -> None:
    """The router API only accepts identifiers, never client-supplied URLs."""
    registry = UpstreamRegistry([_SVC_A])
    router = StaticRouter(registry)

    with pytest.raises(UnknownUpstreamError):
        router.resolve("http://evil.example.com")


def test_static_router_is_a_router() -> None:
    registry = UpstreamRegistry([_SVC_A])
    router = StaticRouter(registry)

    assert isinstance(router, Router)


def test_router_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Router()  # type: ignore[abstract]
