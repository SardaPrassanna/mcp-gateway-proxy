from fastapi import APIRouter
from fastapi.responses import JSONResponse

from mcp_gateway.config.gateway import get_gateway_settings
from mcp_gateway.config.settings import get_application_settings
from mcp_gateway.models.health import HealthStatus, ReadinessStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def get_health() -> HealthStatus:
    """Liveness probe: reports the process is up, without checking configuration."""
    settings = get_application_settings()
    return HealthStatus(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
    )


@router.get("/ready", response_model=None)
def get_readiness() -> ReadinessStatus | JSONResponse:
    """Readiness probe: reports whether gateway configuration loaded successfully."""
    try:
        settings = get_gateway_settings()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return ReadinessStatus(status="ready", upstream_count=len(settings.upstreams))
