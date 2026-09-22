from pydantic import BaseModel, ConfigDict, Field, model_validator


class RateLimitConfig(BaseModel):
    """Rate limiting policy configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    requests_per_minute: int = Field(default=60, gt=0)
    burst: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_burst(self) -> "RateLimitConfig":
        if self.burst is not None and self.burst < self.requests_per_minute:
            raise ValueError("rate_limit.burst must be >= rate_limit.requests_per_minute")
        return self
