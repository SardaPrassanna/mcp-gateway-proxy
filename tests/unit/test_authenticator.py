import pytest

from mcp_gateway.auth.authenticator import ApiKeyAuthenticator
from mcp_gateway.auth.errors import AuthenticationError
from mcp_gateway.config.auth import AuthClient, AuthConfig


def test_disabled_auth_authenticates_anyone_as_anonymous() -> None:
    authenticator = ApiKeyAuthenticator(AuthConfig())

    principal = authenticator.authenticate(None)

    assert principal.client_id == "anonymous"
    assert principal.can_access("anything")


def test_single_key_mode_accepts_the_configured_key() -> None:
    config = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    authenticator = ApiKeyAuthenticator(config)

    principal = authenticator.authenticate("the-key")

    assert principal.client_id == "default"
    assert principal.can_access("any-upstream")


def test_single_key_mode_rejects_wrong_key() -> None:
    config = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    authenticator = ApiKeyAuthenticator(config)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("wrong-key")


def test_enabled_auth_rejects_missing_key() -> None:
    config = AuthConfig(enabled=True, provider="api_key", api_key="the-key")
    authenticator = ApiKeyAuthenticator(config)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(None)


def test_multi_client_mode_resolves_matching_client() -> None:
    config = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[
            AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"database"}),
            AuthClient(client_id="client-b", api_key="key-b"),
        ],
    )
    authenticator = ApiKeyAuthenticator(config)

    principal = authenticator.authenticate("key-a")

    assert principal.client_id == "client-a"
    assert principal.can_access("database") is True
    assert principal.can_access("jira") is False


def test_multi_client_mode_rejects_unknown_key() -> None:
    config = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a")],
    )
    authenticator = ApiKeyAuthenticator(config)

    with pytest.raises(AuthenticationError):
        authenticator.authenticate("not-a-configured-key")


def test_authentication_error_never_contains_the_configured_key() -> None:
    config = AuthConfig(enabled=True, provider="api_key", api_key="super-secret-key")
    authenticator = ApiKeyAuthenticator(config)

    try:
        authenticator.authenticate("wrong-guess")
    except AuthenticationError as exc:
        assert "super-secret-key" not in str(exc)
    else:
        pytest.fail("expected AuthenticationError")


def test_header_name_reflects_configuration() -> None:
    config = AuthConfig(
        enabled=True, provider="api_key", api_key="the-key", api_key_header="X-Custom-Key"
    )
    authenticator = ApiKeyAuthenticator(config)

    assert authenticator.header_name == "X-Custom-Key"
