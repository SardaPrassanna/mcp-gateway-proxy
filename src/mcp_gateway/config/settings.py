from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ApplicationSettings(BaseSettings):
    """Server-level application configuration.

    Sourced from environment variables (prefixed ``MCP_GATEWAY_``) and an
    optional ``.env`` file. Distinct from :class:`~mcp_gateway.config.gateway.GatewaySettings`,
    which holds gateway/upstream policy configuration.
    """

    model_config = SettingsConfigDict(
        env_prefix="MCP_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="mcp-gateway", min_length=1)
    environment: Environment = "development"
    host: str = Field(default="0.0.0.0", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: LogLevel = "INFO"
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)


@lru_cache
def get_application_settings() -> ApplicationSettings:
    return ApplicationSettings()
