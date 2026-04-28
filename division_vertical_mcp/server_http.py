"""
HTTP (Streamable HTTP) transport entry point for Railway deployment.

FastMCP v1.x Streamable HTTP transport:
- MCP endpoint: POST/GET /mcp
- Health check: GET /health  (handled via ASGI mount)
- PORT is injected by Railway via environment variable

Local test:
    PORT=8000 python -m division_vertical_mcp.server_http

Cursor / Claude Code remote MCP connection URL:
    https://<your-app>.up.railway.app/mcp
"""
from __future__ import annotations

import os

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .server import mcp


def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


# Build the ASGI app: /health + /mcp (FastMCP streamable-http)
app = Starlette(
    routes=[
        Route("/health", health),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ]
)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
