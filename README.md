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

## Status

Early development. See commit history for phase-by-phase progress.
