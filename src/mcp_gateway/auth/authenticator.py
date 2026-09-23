import hmac
from typing import Annotated

from fastapi import Depends

from mcp_gateway.auth.errors import AuthenticationError
from mcp_gateway.auth.principal import ANONYMOUS, Principal
from mcp_gateway.config.auth import AuthConfig
from mcp_gateway.config.gateway import GatewaySettings, get_gateway_settings


def _keys_match(presented: str, expected: str) -> bool:
    """Constant-time key comparison that never raises on the caller's input.

    `hmac.compare_digest` rejects `str` arguments containing non-ASCII
    characters with a `TypeError` instead of returning `False`. Comparing
    UTF-8 bytes instead keeps the comparison timing-safe while ensuring a
    malformed (non-ASCII) presented key is simply treated as a mismatch,
    never as an unhandled exception.
    """
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


class ApiKeyAuthenticator:
    """Resolves a presented API key header into a `Principal`.

    When authentication is disabled, every request authenticates as the
    unrestricted anonymous principal, preserving the gateway's safe
    development default. Key comparisons are constant-time and never raise
    on attacker-controlled input, including malformed headers.
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    @property
    def header_name(self) -> str:
        return self._config.api_key_header

    def authenticate(self, presented_key: str | None) -> Principal:
        if not self._config.enabled:
            return ANONYMOUS

        if not presented_key:
            raise AuthenticationError("missing API key")

        for client in self._config.clients:
            if _keys_match(presented_key, client.api_key.get_secret_value()):
                return Principal(
                    client_id=client.client_id, allowed_upstreams=client.allowed_upstreams
                )

        global_key = self._config.api_key
        if (
            not self._config.clients
            and global_key is not None
            and _keys_match(presented_key, global_key.get_secret_value())
        ):
            return Principal(client_id="default", allowed_upstreams=None)

        raise AuthenticationError("invalid API key")


def get_authenticator(
    gateway_settings: Annotated[GatewaySettings, Depends(get_gateway_settings)],
) -> ApiKeyAuthenticator:
    return ApiKeyAuthenticator(gateway_settings.auth)
