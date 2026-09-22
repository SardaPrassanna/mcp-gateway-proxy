"""Focused coverage of the upstream registry and routing security model.

Complements test_registry.py and test_router.py with explicit success and
failure paths for the scenarios the routing layer exists to guarantee:
clients can only reach upstreams the gateway operator configured, by the
identifier the operator assigned, and never by a URL the client supplies.
"""

import pytest

from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.routing.errors import UnknownUpstreamError
from mcp_gateway.routing.registry import UpstreamRegistry
from mcp_gateway.routing.router import StaticRouter

_SVC_A = UpstreamServerConfig(name="svc-a", url="http://localhost:9001")
_SVC_B = UpstreamServerConfig(name="svc-b", url="http://localhost:9002")


def test_known_upstream_resolves_correctly() -> None:
    router = StaticRouter(UpstreamRegistry([_SVC_A, _SVC_B]))

    assert router.resolve("svc-a") is _SVC_A


def test_unknown_upstream_is_rejected() -> None:
    router = StaticRouter(UpstreamRegistry([_SVC_A]))

    with pytest.raises(UnknownUpstreamError):
        router.resolve("svc-does-not-exist")


def test_duplicate_upstream_ids_are_rejected_at_construction() -> None:
    clashing = UpstreamServerConfig(name="svc-a", url="http://localhost:9999")

    with pytest.raises(ValueError, match="duplicate upstream name"):
        UpstreamRegistry([_SVC_A, clashing])


def test_disabled_upstream_cannot_be_resolved() -> None:
    disabled = UpstreamServerConfig(name="svc-a", url="http://localhost:9001", enabled=False)
    registry = UpstreamRegistry([disabled])

    assert "svc-a" not in registry
    with pytest.raises(UnknownUpstreamError):
        registry.get("svc-a")
    with pytest.raises(UnknownUpstreamError):
        StaticRouter(registry).resolve("svc-a")


def test_disabled_upstream_is_indistinguishable_from_unknown() -> None:
    """Disabled upstreams must not leak their existence to callers."""
    disabled = UpstreamServerConfig(name="svc-a", url="http://localhost:9001", enabled=False)
    registry = UpstreamRegistry([disabled])

    try:
        registry.get("svc-a")
        pytest.fail("expected UnknownUpstreamError")
    except UnknownUpstreamError as exc:
        disabled_error_type = type(exc)

    try:
        registry.get("svc-genuinely-unconfigured")
        pytest.fail("expected UnknownUpstreamError")
    except UnknownUpstreamError as exc:
        unknown_error_type = type(exc)

    assert disabled_error_type is unknown_error_type


def test_disabling_one_upstream_does_not_affect_others() -> None:
    disabled = UpstreamServerConfig(name="svc-a", url="http://localhost:9001", enabled=False)
    registry = UpstreamRegistry([disabled, _SVC_B])
    router = StaticRouter(registry)

    with pytest.raises(UnknownUpstreamError):
        router.resolve("svc-a")
    assert router.resolve("svc-b") is _SVC_B


def test_configured_url_is_used_unmodified() -> None:
    router = StaticRouter(UpstreamRegistry([_SVC_A]))

    resolved = router.resolve("svc-a")

    assert str(resolved.url) == "http://localhost:9001/"


def test_arbitrary_client_supplied_url_cannot_override_routing() -> None:
    """The router only ever accepts a configured identifier, never a URL."""
    router = StaticRouter(UpstreamRegistry([_SVC_A]))

    with pytest.raises(UnknownUpstreamError):
        router.resolve("http://attacker.example.com")

    with pytest.raises(UnknownUpstreamError):
        router.resolve(str(_SVC_A.url))


def test_routing_with_multiple_upstream_servers_is_independent() -> None:
    svc_c = UpstreamServerConfig(name="svc-c", url="http://localhost:9003")
    router = StaticRouter(UpstreamRegistry([_SVC_A, _SVC_B, svc_c]))

    assert router.resolve("svc-a") is _SVC_A
    assert router.resolve("svc-b") is _SVC_B
    assert router.resolve("svc-c") is svc_c
    with pytest.raises(UnknownUpstreamError):
        router.resolve("svc-d")


def test_empty_registry_rejects_every_lookup() -> None:
    router = StaticRouter(UpstreamRegistry([]))

    with pytest.raises(UnknownUpstreamError):
        router.resolve("svc-a")
