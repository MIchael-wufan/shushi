"""
HTTP (Streamable HTTP) transport entry point for Railway deployment.

FastMCP v1.x Streamable HTTP transport:
- MCP endpoint: POST/GET /mcp  (FastMCP default streamable_http_path="/mcp")
- Health check: GET /health
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
from starlette.routing import Route

from .server import mcp


def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


# FastMCP streamable_http_app() already handles /mcp internally.
# Mount it at root "/" so the full path stays /mcp.
_mcp_asgi = mcp.streamable_http_app()


async def app(scope, receive, send):
    if scope["type"] == "http" and scope["path"] == "/health":
        req = Request(scope, receive)
        resp = health(req)
        await resp(scope, receive, send)
    else:
        await _mcp_asgi(scope, receive, send)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("division_vertical_mcp.server_http:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
