import logging

import httpx
import pytest

from mcp_gateway.auth.authenticator import ApiKeyAuthenticator, get_authenticator
from mcp_gateway.config.auth import AuthConfig
from mcp_gateway.config.upstream import UpstreamServerConfig
from mcp_gateway.observability.audit import AUDIT_LOGGER_NAME
from tests.integration.conftest import (
    DependencyOverrides,
    GatewayFactory,
    RecordingTransport,
    json_echo_upstream,
)


def _auth_override(auth: AuthConfig) -> DependencyOverrides:
    return {get_authenticator: lambda: ApiKeyAuthenticator(auth)}


async def test_readiness_endpoint_reports_ready_with_upstream_count(
    gateway_factory: GatewayFactory,
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    client = await gateway_factory([upstream], httpx.ASGITransport(app=json_echo_upstream))

    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_health_and_readiness_responses_carry_a_correlation_id(
    gateway_factory: GatewayFactory,
) -> None:
    client = await gateway_factory([], httpx.ASGITransport(app=json_echo_upstream))

    health_response = await client.get("/health")
    ready_response = await client.get("/ready")

    assert "x-request-id" in health_response.headers
    assert "x-request-id" in ready_response.headers


async def test_access_log_records_method_path_status_and_duration(
    gateway_factory: GatewayFactory, caplog: pytest.LogCaptureFixture
) -> None:
    client = await gateway_factory([], httpx.ASGITransport(app=json_echo_upstream))

    with caplog.at_level(logging.INFO, logger="mcp_gateway.access"):
        response = await client.get("/health")

    record = next(r for r in caplog.records if r.name == "mcp_gateway.access")
    assert record.method == "GET"  # type: ignore[attr-defined]
    assert record.path == "/health"  # type: ignore[attr-defined]
    assert record.status_code == 200  # type: ignore[attr-defined]
    assert record.duration_ms >= 0  # type: ignore[attr-defined]
    assert record.correlation_id == response.headers["x-request-id"]  # type: ignore[attr-defined]


async def test_successful_forward_emits_authentication_and_forwarding_audit_events(
    gateway_factory: GatewayFactory, caplog: pytest.LogCaptureFixture
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        await client.post("/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "the-key"})

    events = [r.event for r in caplog.records if r.name == AUDIT_LOGGER_NAME]  # type: ignore[attr-defined]
    assert "authentication_succeeded" in events
    assert "request_forwarded" in events

    forwarded_record = next(
        r for r in caplog.records if getattr(r, "event", None) == "request_forwarded"
    )
    assert forwarded_record.upstream == "svc-a"  # type: ignore[attr-defined]
    assert forwarded_record.status_code == 200  # type: ignore[attr-defined]
    assert forwarded_record.duration_ms >= 0  # type: ignore[attr-defined]


async def test_authentication_failure_emits_audit_event_without_leaking_the_key(
    gateway_factory: GatewayFactory, caplog: pytest.LogCaptureFixture
) -> None:
    upstream = UpstreamServerConfig(name="svc-a", url="http://fake-upstream.test/mcp")
    transport = RecordingTransport()
    auth = AuthConfig(enabled=True, provider="api_key", api_key="the-real-key")
    client = await gateway_factory([upstream], transport, dependency_overrides=_auth_override(auth))

    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        await client.post(
            "/mcp/svc-a", json={"jsonrpc": "2.0"}, headers={"X-API-Key": "wrong-guess"}
        )

    audit_records = [r for r in caplog.records if r.name == AUDIT_LOGGER_NAME]
    assert any(getattr(r, "event", None) == "authentication_failed" for r in audit_records)
    assert "the-real-key" not in caplog.text
    assert "wrong-guess" not in caplog.text


async def test_unknown_upstream_emits_audit_event_with_the_requested_id(
    gateway_factory: GatewayFactory, caplog: pytest.LogCaptureFixture
) -> None:
    client = await gateway_factory([], httpx.ASGITransport(app=json_echo_upstream))

    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        await client.post("/mcp/does-not-exist", json={"jsonrpc": "2.0"})

    record = next(
        r for r in caplog.records if getattr(r, "event", None) == "unknown_upstream_rejected"
    )
    assert record.upstream_id == "does-not-exist"  # type: ignore[attr-defined]
