from mcp_gateway.models.health import HealthStatus


def test_health_status_serialization() -> None:
    health = HealthStatus(status="ok", app_name="mcp-gateway", environment="test")

    assert health.model_dump() == {
        "status": "ok",
        "app_name": "mcp-gateway",
        "environment": "test",
    }
