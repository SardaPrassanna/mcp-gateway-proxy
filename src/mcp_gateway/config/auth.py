from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

AuthProvider = Literal["none", "api_key", "bearer"]


class AuthConfig(BaseModel):
    """Authentication policy configuration.

    Defines *what* authentication the gateway is configured to expect; actual
    enforcement is implemented by a later authentication phase.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    provider: AuthProvider = "none"
    api_key_header: str = Field(default="X-API-Key", min_length=1)
    api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _validate_provider_consistency(self) -> "AuthConfig":
        if self.enabled and self.provider == "none":
            raise ValueError("auth.enabled requires a provider other than 'none'")
        if self.provider == "api_key" and self.enabled and self.api_key is None:
            raise ValueError("auth.api_key must be set when provider is 'api_key' and enabled")
        return self
