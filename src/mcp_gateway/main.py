import uvicorn
from fastapi import FastAPI

from mcp_gateway.api.health import router as health_router
from mcp_gateway.config.settings import get_application_settings


def create_app() -> FastAPI:
    settings = get_application_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router)
    return app


app = create_app()


def run() -> None:
    """Entry point for the `mcp-gateway` console script."""
    settings = get_application_settings()
    uvicorn.run(
        "mcp_gateway.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
