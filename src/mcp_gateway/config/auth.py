import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

AuthProvider = Literal["none", "api_key", "bearer"]

_CLIENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class AuthClient(BaseModel):
    """A single authenticated principal and the upstreams it may reach.

    `allowed_upstreams` is an explicit allowlist: `None` permits access to any
    configured upstream, while a set restricts the client to exactly those
    names. There is no "denied" list — anything not allowlisted is denied by
    default, which keeps the authorization decision a single lookup.
    """

    model_config = ConfigDict(frozen=True)

    client_id: str = Field(min_length=1, max_length=64)
    api_key: SecretStr
    allowed_upstreams: frozenset[str] | None = Field(
        default=None,
        description="Upstream names this client may access; None means all upstreams.",
    )

    @model_validator(mode="after")
    def _validate_client_id(self) -> "AuthClient":
        if not _CLIENT_ID_PATTERN.match(self.client_id):
            raise ValueError(
                f"client id {self.client_id!r} must contain only letters, digits, '-' or '_'"
            )
        return self


class AuthConfig(BaseModel):
    """Authentication and authorization policy configuration.

    Defines *what* authentication the gateway is configured to expect; actual
    enforcement lives in `mcp_gateway.auth`.

    Two modes are supported when `enabled` and `provider == "api_key"`:

    - single-key mode: `api_key` is set and `clients` is empty. Any request
      presenting that key is authenticated and may reach any upstream.
    - multi-client mode: `clients` is non-empty. Each client has its own key
      and its own upstream allowlist, matching a policy such as::

          client-a:
              database: allowed
              github: allowed
              jira: denied
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    provider: AuthProvider = "none"
    api_key_header: str = Field(default="X-API-Key", min_length=1)
    api_key: SecretStr | None = None
    clients: list[AuthClient] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_provider_consistency(self) -> "AuthConfig":
        if self.enabled and self.provider == "none":
            raise ValueError("auth.enabled requires a provider other than 'none'")
        needs_credential = self.provider == "api_key" and self.enabled
        if needs_credential and self.api_key is None and not self.clients:
            raise ValueError(
                "auth.api_key or auth.clients must be set when provider is 'api_key' and enabled"
            )
        return self

    @model_validator(mode="after")
    def _validate_unique_clients(self) -> "AuthConfig":
        client_ids = [client.client_id for client in self.clients]
        duplicate_ids = {client_id for client_id in client_ids if client_ids.count(client_id) > 1}
        if duplicate_ids:
            raise ValueError(f"duplicate auth client ids configured: {sorted(duplicate_ids)}")

        keys = [client.api_key.get_secret_value() for client in self.clients]
        if len(set(keys)) != len(keys):
            raise ValueError("auth clients must each have a distinct api_key")
        return self
