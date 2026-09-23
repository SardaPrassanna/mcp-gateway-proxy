from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Response schema for the liveness health endpoint."""

    status: str
    app_name: str
    environment: str


class ReadinessStatus(BaseModel):
    """Response schema for the readiness endpoint."""

    status: str
    upstream_count: int
