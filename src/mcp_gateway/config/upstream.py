import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class UpstreamServerConfig(BaseModel):
    """Configuration for a single upstream MCP server the gateway may forward to."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=64)
    url: HttpUrl
    description: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0, le=300)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not _NAME_PATTERN.match(value):
            raise ValueError(
                f"upstream name {value!r} must contain only letters, digits, '-' or '_'"
            )
        return value
