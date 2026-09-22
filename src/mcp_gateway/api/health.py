from fastapi import APIRouter

from mcp_gateway.config.settings import get_settings
from mcp_gateway.models.health import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def get_health() -> HealthStatus:
    settings = get_settings()
    return HealthStatus(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
    )
