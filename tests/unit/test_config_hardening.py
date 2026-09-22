"""Hardening tests for the configuration layer (Phase 3).

These tests exercise observable behavior of the public configuration API
(construction, validation errors, and serialization) rather than internal
implementation details.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings.exceptions import SettingsError

from mcp_gateway.config.auth import AuthConfig
from mcp_gateway.config.gateway import GatewaySettings
from mcp_gateway.config.rate_limit import RateLimitConfig
from mcp_gateway.config.settings import ApplicationSettings
from mcp_gateway.config.upstream import UpstreamServerConfig

# ---------------------------------------------------------------------------
# 1. Valid configuration
# ---------------------------------------------------------------------------


def test_full_valid_configuration_composes_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_APP_NAME", "acceptance-gateway")
    monkeypatch.setenv("MCP_GATEWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("MCP_GATEWAY_PORT", "8443")
    monkeypatch.setenv(
        "MCP_GATEWAY_UPSTREAMS",
        json.dumps(
            [
                {"name": "svc-a", "url": "http://localhost:9001"},
                {"name": "svc-b", "url": "http://localhost:9002", "timeout_seconds": 5},
            ]
        ),
    )
    monkeypatch.setenv("MCP_GATEWAY_AUTH__ENABLED", "true")
    monkeypatch.setenv("MCP_GATEWAY_AUTH__PROVIDER", "api_key")
    monkeypatch.setenv("MCP_GATEWAY_AUTH__API_KEY", "valid-secret")
    monkeypatch.setenv("MCP_GATEWAY_RATE_LIMIT__ENABLED", "true")
    monkeypatch.setenv("MCP_GATEWAY_RATE_LIMIT__REQUESTS_PER_MINUTE", "100")
    monkeypatch.setenv("MCP_GATEWAY_RATE_LIMIT__BURST", "200")

    app_settings = ApplicationSettings()
    gateway_settings = GatewaySettings()

    assert app_settings.app_name == "acceptance-gateway"
    assert app_settings.environment == "production"
    assert app_settings.port == 8443
    assert [u.name for u in gateway_settings.upstreams] == ["svc-a", "svc-b"]
    assert gateway_settings.auth.enabled is True
    assert gateway_settings.rate_limit.burst == 200


# ---------------------------------------------------------------------------
# 2. Invalid port
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_port", ["0", "-1", "65536", "not-a-port"])
def test_settings_rejects_invalid_port_values(
    monkeypatch: pytest.MonkeyPatch, invalid_port: str
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_PORT", invalid_port)

    with pytest.raises(ValidationError):
        ApplicationSettings()


def test_settings_accepts_boundary_port_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_GATEWAY_PORT", "1")
    assert ApplicationSettings().port == 1

    monkeypatch.setenv("MCP_GATEWAY_PORT", "65535")
    assert ApplicationSettings().port == 65535


# ---------------------------------------------------------------------------
# 3. Invalid timeout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_timeout", ["0", "-5", "301"])
def test_settings_rejects_invalid_request_timeout(
    monkeypatch: pytest.MonkeyPatch, invalid_timeout: str
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_REQUEST_TIMEOUT_SECONDS", invalid_timeout)

    with pytest.raises(ValidationError):
        ApplicationSettings()


def test_upstream_rejects_timeout_above_maximum() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="example", url="http://localhost:9000", timeout_seconds=301)


# ---------------------------------------------------------------------------
# 4. Malformed upstream configuration
# ---------------------------------------------------------------------------


def test_upstream_rejects_missing_name_and_url() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UpstreamServerConfig()  # type: ignore[call-arg]

    missing_fields = {error["loc"][0] for error in exc_info.value.errors()}
    assert missing_fields == {"name", "url"}


def test_upstream_rejects_name_exceeding_max_length() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="x" * 65, url="http://localhost:9000")


def test_upstream_rejects_non_string_url_type() -> None:
    with pytest.raises(ValidationError):
        UpstreamServerConfig(name="example", url=12345)


def test_gateway_settings_rejects_malformed_json_in_upstreams_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_UPSTREAMS", "{not-valid-json")

    with pytest.raises(SettingsError):
        GatewaySettings()


def test_gateway_settings_rejects_upstream_missing_url_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_UPSTREAMS", json.dumps([{"name": "svc-a"}]))

    with pytest.raises(ValidationError):
        GatewaySettings()


# ---------------------------------------------------------------------------
# 5. Duplicate upstream identifiers
# ---------------------------------------------------------------------------


def test_gateway_settings_rejects_duplicate_names_among_three_upstreams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MCP_GATEWAY_UPSTREAMS",
        json.dumps(
            [
                {"name": "svc-a", "url": "http://localhost:9001"},
                {"name": "svc-b", "url": "http://localhost:9002"},
                {"name": "svc-a", "url": "http://localhost:9003"},
            ]
        ),
    )

    with pytest.raises(ValidationError) as exc_info:
        GatewaySettings()

    assert "svc-a" in str(exc_info.value)


def test_gateway_settings_treats_differently_cased_names_as_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MCP_GATEWAY_UPSTREAMS",
        json.dumps(
            [
                {"name": "svc-a", "url": "http://localhost:9001"},
                {"name": "SVC-A", "url": "http://localhost:9002"},
            ]
        ),
    )

    settings = GatewaySettings()

    assert {u.name for u in settings.upstreams} == {"svc-a", "SVC-A"}


# ---------------------------------------------------------------------------
# 6. Missing required configuration
# ---------------------------------------------------------------------------


def test_upstream_requires_name() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UpstreamServerConfig(url="http://localhost:9000")  # type: ignore[call-arg]

    assert exc_info.value.errors()[0]["loc"] == ("name",)


def test_upstream_requires_url() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UpstreamServerConfig(name="example")  # type: ignore[call-arg]

    assert exc_info.value.errors()[0]["loc"] == ("url",)


def test_gateway_settings_has_no_required_fields_and_uses_safe_defaults() -> None:
    settings = GatewaySettings()

    assert settings.upstreams == []
    assert settings.auth == AuthConfig()
    assert settings.rate_limit == RateLimitConfig()


# ---------------------------------------------------------------------------
# 7. Environment variable overrides
# ---------------------------------------------------------------------------


def test_environment_variable_overrides_application_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert ApplicationSettings().log_level == "INFO"

    monkeypatch.setenv("MCP_GATEWAY_LOG_LEVEL", "DEBUG")

    assert ApplicationSettings().log_level == "DEBUG"


def test_explicit_constructor_argument_takes_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_APP_NAME", "from-environment")

    settings = ApplicationSettings(app_name="from-explicit-argument")

    assert settings.app_name == "from-explicit-argument"


def test_config_file_env_var_pointing_to_missing_file_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_file = tmp_path / "does-not-exist.json"
    monkeypatch.setenv("MCP_GATEWAY_CONFIG_FILE", str(missing_file))

    settings = GatewaySettings()

    assert settings.upstreams == []


# ---------------------------------------------------------------------------
# 8. Secret values are not exposed through normal representation/logging
# ---------------------------------------------------------------------------


_RAW_SECRET = "super-secret-token-value"


def test_secret_not_exposed_in_gateway_settings_repr() -> None:
    settings = GatewaySettings(
        auth=AuthConfig(enabled=True, provider="api_key", api_key=_RAW_SECRET)
    )

    assert _RAW_SECRET not in repr(settings)
    assert _RAW_SECRET not in str(settings)


def test_secret_not_exposed_in_gateway_settings_model_dump_json() -> None:
    settings = GatewaySettings(
        auth=AuthConfig(enabled=True, provider="api_key", api_key=_RAW_SECRET)
    )

    dumped_json = settings.model_dump_json()

    assert _RAW_SECRET not in dumped_json
    assert "**********" in dumped_json


def test_secret_not_exposed_in_gateway_settings_model_dump() -> None:
    settings = GatewaySettings(
        auth=AuthConfig(enabled=True, provider="api_key", api_key=_RAW_SECRET)
    )

    dumped = settings.model_dump()

    assert _RAW_SECRET not in str(dumped)


def test_secret_not_exposed_when_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_GATEWAY_AUTH__ENABLED", "true")
    monkeypatch.setenv("MCP_GATEWAY_AUTH__PROVIDER", "api_key")
    monkeypatch.setenv("MCP_GATEWAY_AUTH__API_KEY", _RAW_SECRET)

    settings = GatewaySettings()

    assert _RAW_SECRET not in repr(settings)
    assert _RAW_SECRET not in settings.model_dump_json()
