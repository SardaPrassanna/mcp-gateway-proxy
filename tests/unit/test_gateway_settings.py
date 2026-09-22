import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mcp_gateway.config.gateway import GatewaySettings


def test_gateway_settings_defaults() -> None:
    settings = GatewaySettings()

    assert settings.upstreams == []
    assert settings.auth.enabled is False
    assert settings.rate_limit.enabled is False


def test_gateway_settings_reads_upstreams_from_json_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MCP_GATEWAY_UPSTREAMS",
        json.dumps([{"name": "svc-a", "url": "http://localhost:9001"}]),
    )

    settings = GatewaySettings()

    assert len(settings.upstreams) == 1
    assert settings.upstreams[0].name == "svc-a"


def test_gateway_settings_reads_nested_auth_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_AUTH__ENABLED", "true")
    monkeypatch.setenv("MCP_GATEWAY_AUTH__PROVIDER", "api_key")
    monkeypatch.setenv("MCP_GATEWAY_AUTH__API_KEY", "env-secret")

    settings = GatewaySettings()

    assert settings.auth.enabled is True
    assert settings.auth.provider == "api_key"
    assert settings.auth.api_key is not None
    assert settings.auth.api_key.get_secret_value() == "env-secret"


def test_gateway_settings_rejects_duplicate_upstream_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MCP_GATEWAY_UPSTREAMS",
        json.dumps(
            [
                {"name": "svc-a", "url": "http://localhost:9001"},
                {"name": "svc-a", "url": "http://localhost:9002"},
            ]
        ),
    )

    with pytest.raises(ValidationError):
        GatewaySettings()


def test_gateway_settings_loads_upstreams_from_config_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "gateway.config.json"
    config_file.write_text(
        json.dumps({"upstreams": [{"name": "file-svc", "url": "http://localhost:9500"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_GATEWAY_CONFIG_FILE", str(config_file))

    settings = GatewaySettings()

    assert len(settings.upstreams) == 1
    assert settings.upstreams[0].name == "file-svc"


def test_gateway_settings_environment_overrides_config_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "gateway.config.json"
    config_file.write_text(
        json.dumps({"upstreams": [{"name": "file-svc", "url": "http://localhost:9500"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_GATEWAY_CONFIG_FILE", str(config_file))
    monkeypatch.setenv(
        "MCP_GATEWAY_UPSTREAMS",
        json.dumps([{"name": "env-svc", "url": "http://localhost:9600"}]),
    )

    settings = GatewaySettings()

    assert len(settings.upstreams) == 1
    assert settings.upstreams[0].name == "env-svc"
