import pytest

from mcp_gateway.config.settings import Settings


def test_settings_default_values() -> None:
    settings = Settings()

    assert settings.app_name == "mcp-gateway"
    assert settings.environment == "development"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.log_level == "INFO"


def test_settings_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_APP_NAME", "custom-gateway")
    monkeypatch.setenv("MCP_GATEWAY_PORT", "9000")

    settings = Settings()

    assert settings.app_name == "custom-gateway"
    assert settings.port == 9000
