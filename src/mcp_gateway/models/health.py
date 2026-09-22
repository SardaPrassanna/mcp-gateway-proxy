from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Response schema for the health endpoint."""

    status: str
    app_name: str
    environment: str
