# MCP Gateway / Proxy

A production-grade gateway and proxy for the Model Context Protocol (MCP), built incrementally as a portfolio engineering project.

## Overview

This project implements a gateway that sits in front of multiple upstream MCP servers, forwarding MCP requests over Streamable HTTP while providing the operational concerns expected of a production system: authentication, authorization, rate limiting, structured logging, request correlation, health checks, and more.

The project is built in phases, with each phase independently runnable and validated (formatting, linting, type checking, tests) before being committed.

## Technology

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- FastAPI / ASGI
- Official MCP Python SDK
- Pydantic / pydantic-settings
- pytest / pytest-asyncio
- httpx
- Ruff
- mypy
- Docker

## Scope (initial version)

- MCP over Streamable HTTP
- JSON-RPC/MCP request forwarding
- Multiple configured upstream MCP servers

stdio proxying and other extensions are out of scope until an explicit later phase.

## Project structure

```
src/mcp_gateway/
    main.py            # Application entry point (FastAPI app + ASGI server)
    config/             # Settings and configuration loading
    api/                 # HTTP route handlers
    auth/               # Authentication (future phase)
    middleware/          # ASGI/HTTP middleware (future phase)
    proxy/              # MCP request forwarding (future phase)
    routing/             # Upstream server routing (future phase)
    models/              # Pydantic models/schemas
    observability/        # Logging, metrics, tracing (future phase)
    security/            # Security controls (future phase)
    services/            # Application services

tests/
    unit/               # Unit tests
    integration/          # Integration tests (e.g. HTTP endpoint tests)

docs/                    # Project documentation
```

## Getting started

```bash
uv sync
cp .env.example .env
uv run mcp-gateway
```

The application exposes a health check at `GET /health`.

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

## Status

Early development. See commit history for phase-by-phase progress.
