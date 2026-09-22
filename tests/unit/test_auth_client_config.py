import pytest
from pydantic import ValidationError

from mcp_gateway.config.auth import AuthClient, AuthConfig
from mcp_gateway.config.gateway import GatewaySettings
from mcp_gateway.config.upstream import UpstreamServerConfig


def test_auth_config_defaults_have_no_clients() -> None:
    auth = AuthConfig()

    assert auth.clients == []


def test_multi_client_mode_satisfies_api_key_provider_requirement() -> None:
    auth = AuthConfig(
        enabled=True,
        provider="api_key",
        clients=[AuthClient(client_id="client-a", api_key="key-a")],
    )

    assert auth.enabled is True
    assert auth.clients[0].client_id == "client-a"


def test_rejects_client_id_with_invalid_characters() -> None:
    with pytest.raises(ValidationError):
        AuthClient(client_id="client a!", api_key="key-a")


def test_rejects_duplicate_client_ids() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(
            enabled=True,
            provider="api_key",
            clients=[
                AuthClient(client_id="client-a", api_key="key-1"),
                AuthClient(client_id="client-a", api_key="key-2"),
            ],
        )


def test_rejects_duplicate_api_keys_across_clients() -> None:
    with pytest.raises(ValidationError):
        AuthConfig(
            enabled=True,
            provider="api_key",
            clients=[
                AuthClient(client_id="client-a", api_key="shared-key"),
                AuthClient(client_id="client-b", api_key="shared-key"),
            ],
        )


def test_client_never_exposes_api_key_in_repr() -> None:
    client = AuthClient(client_id="client-a", api_key="super-secret")

    assert "super-secret" not in repr(client)
    assert "super-secret" not in str(client)


def test_client_allowed_upstreams_defaults_to_unrestricted() -> None:
    client = AuthClient(client_id="client-a", api_key="key-a")

    assert client.allowed_upstreams is None


def test_client_allowed_upstreams_can_be_restricted() -> None:
    client = AuthClient(
        client_id="client-a", api_key="key-a", allowed_upstreams={"database", "github"}
    )

    assert client.allowed_upstreams == frozenset({"database", "github"})


def test_gateway_settings_rejects_client_referencing_unknown_upstream() -> None:
    with pytest.raises(ValidationError):
        GatewaySettings(
            upstreams=[UpstreamServerConfig(name="database", url="http://db.internal")],
            auth=AuthConfig(
                enabled=True,
                provider="api_key",
                clients=[
                    AuthClient(client_id="client-a", api_key="key-a", allowed_upstreams={"jira"})
                ],
            ),
        )


def test_gateway_settings_accepts_client_referencing_known_upstream() -> None:
    settings = GatewaySettings(
        upstreams=[
            UpstreamServerConfig(name="database", url="http://db.internal"),
            UpstreamServerConfig(name="github", url="http://github.internal"),
        ],
        auth=AuthConfig(
            enabled=True,
            provider="api_key",
            clients=[
                AuthClient(
                    client_id="client-a",
                    api_key="key-a",
                    allowed_upstreams={"database", "github"},
                )
            ],
        ),
    )

    assert settings.auth.clients[0].allowed_upstreams == frozenset({"database", "github"})
