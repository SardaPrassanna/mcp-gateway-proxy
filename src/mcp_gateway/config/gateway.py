import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from mcp_gateway.config.auth import AuthConfig
from mcp_gateway.config.rate_limit import RateLimitConfig
from mcp_gateway.config.upstream import UpstreamServerConfig

CONFIG_FILE_ENV_VAR = "MCP_GATEWAY_CONFIG_FILE"


class GatewaySettings(BaseSettings):
    """Gateway/upstream policy configuration.

    Distinct from :class:`~mcp_gateway.config.settings.ApplicationSettings`, which holds
    server-level configuration. Values may be supplied via environment variables
    (prefixed ``MCP_GATEWAY_``, JSON-encoded for list/object fields), a ``.env``
    file, or an optional JSON configuration file pointed to by the
    ``MCP_GATEWAY_CONFIG_FILE`` environment variable. Environment variables take
    precedence over the configuration file.
    """

    model_config = SettingsConfigDict(
        env_prefix="MCP_GATEWAY_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    upstreams: list[UpstreamServerConfig] = Field(default_factory=list)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    @field_validator("upstreams")
    @classmethod
    def _validate_unique_names(
        cls, value: list[UpstreamServerConfig]
    ) -> list[UpstreamServerConfig]:
        names = [upstream.name for upstream in value]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(f"duplicate upstream names configured: {sorted(duplicates)}")
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings, dotenv_settings]

        config_file = os.environ.get(CONFIG_FILE_ENV_VAR)
        if config_file:
            sources.append(JsonConfigSettingsSource(settings_cls, json_file=config_file))

        sources.append(file_secret_settings)
        return tuple(sources)


@lru_cache
def get_gateway_settings() -> GatewaySettings:
    return GatewaySettings()
