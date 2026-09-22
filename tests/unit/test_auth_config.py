import pytest
from pydantic import ValidationError

from mcp_gateway.config.auth import AuthConfig


def test_auth_config_defaults_to_disabled() -> None:
    auth = AuthConfig()

    assert auth.enabled is False
    assert auth.provider == "none"
    assert auth.api_key is None


def test_auth_config_rejects_enabled_with_no_provider() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(enabled=True, provider="none")


def test_auth_config_rejects_api_key_provider_without_key() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(enabled=True, provider="api_key")


def test_auth_config_accepts_api_key_provider_with_key() -> None:
    auth = AuthConfig(enabled=True, provider="api_key", api_key="secret-value")

    assert auth.enabled is True
    assert auth.api_key is not None
    assert auth.api_key.get_secret_value() == "secret-value"


def test_auth_config_never_exposes_secret_in_repr() -> None:
    auth = AuthConfig(enabled=True, provider="api_key", api_key="super-secret")

    assert "super-secret" not in repr(auth)
    assert "super-secret" not in str(auth)
