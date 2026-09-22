from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from mcp_gateway.api.health import router as health_router
from mcp_gateway.api.mcp import router as mcp_router
from mcp_gateway.config.settings import get_application_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    settings = get_application_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(mcp_router)
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
