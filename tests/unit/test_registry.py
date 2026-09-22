import pytest

from mcp_gateway.config.gateway import GatewaySettings
from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.routing.errors import UnknownUpstreamError
from mcp_gateway.routing.registry import UpstreamRegistry

_SVC_A = UpstreamServerConfig(name="svc-a", url="http://localhost:9001")
_SVC_B = UpstreamServerConfig(name="svc-b", url="http://localhost:9002")


def test_registry_get_returns_configured_upstream() -> None:
    registry = UpstreamRegistry([_SVC_A, _SVC_B])

    assert registry.get("svc-a") is _SVC_A
    assert registry.get("svc-b") is _SVC_B


def test_registry_get_unknown_id_raises() -> None:
    registry = UpstreamRegistry([_SVC_A])

    with pytest.raises(UnknownUpstreamError):
        registry.get("does-not-exist")


def test_registry_contains() -> None:
    registry = UpstreamRegistry([_SVC_A])

    assert "svc-a" in registry
    assert "svc-b" not in registry


def test_registry_iteration_and_len() -> None:
    registry = UpstreamRegistry([_SVC_A, _SVC_B])

    assert len(registry) == 2
    assert {upstream.name for upstream in registry} == {"svc-a", "svc-b"}


def test_registry_ids() -> None:
    registry = UpstreamRegistry([_SVC_A, _SVC_B])

    assert registry.ids == frozenset({"svc-a", "svc-b"})


def test_registry_rejects_duplicate_names() -> None:
    duplicate = UpstreamServerConfig(name="svc-a", url="http://localhost:9999")

    with pytest.raises(ValueError, match="duplicate upstream name"):
        UpstreamRegistry([_SVC_A, duplicate])


def test_registry_is_case_sensitive() -> None:
    registry = UpstreamRegistry([_SVC_A])

    with pytest.raises(UnknownUpstreamError):
        registry.get("SVC-A")


def test_registry_from_settings_builds_from_gateway_settings() -> None:
    settings = GatewaySettings(upstreams=[_SVC_A, _SVC_B])

    registry = UpstreamRegistry.from_settings(settings)

    assert registry.ids == frozenset({"svc-a", "svc-b"})


def test_registry_empty_by_default() -> None:
    registry = UpstreamRegistry([])

    assert len(registry) == 0
    assert registry.ids == frozenset()
