import pytest
from pydantic import ValidationError

from mcp_gateway.config.settings import ApplicationSettings


def test_settings_default_values() -> None:
    settings = ApplicationSettings()

    assert settings.app_name == "mcp-gateway"
    assert settings.environment == "development"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.log_level == "INFO"
    assert settings.request_timeout_seconds == 30.0


def test_settings_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_APP_NAME", "custom-gateway")
    monkeypatch.setenv("MCP_GATEWAY_PORT", "9000")
    monkeypatch.setenv("MCP_GATEWAY_ENVIRONMENT", "production")

    settings = ApplicationSettings()

    assert settings.app_name == "custom-gateway"
    assert settings.port == 9000
    assert settings.environment == "production"


def test_settings_rejects_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_ENVIRONMENT", "not-a-real-environment")

    with pytest.raises(ValidationError):
        ApplicationSettings()


def test_settings_rejects_out_of_range_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_PORT", "70000")

    with pytest.raises(ValidationError):
        ApplicationSettings()


def test_settings_rejects_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError):
        ApplicationSettings()


def test_settings_rejects_non_positive_request_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_REQUEST_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        ApplicationSettings()
