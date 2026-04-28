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
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from .compose import (
    build_addition_vertical_svg,
    build_combined_svg,
    build_integer_division_vertical_svg,
    build_multiplication_vertical_svg,
    build_subtraction_vertical_svg,
)
from .oss_store import mcp_svg_text_to_tool_output

# Re-create mcp with DNS rebinding protection disabled for public Railway deployment
mcp = FastMCP(
    "division-vertical",
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


@mcp.tool()
def render_division_vertical(
    dividend: str,
    divisor: str,
    include_verification: bool = False,
    retain_decimal_places: int | None = None,
) -> str:
    """
    根据被除数、除数生成教材风格除法竖式图（网格对齐）。
    """
    return mcp_svg_text_to_tool_output(
        build_combined_svg(
            dividend,
            divisor,
            include_verification=include_verification,
            retain_decimal_places=retain_decimal_places,
        )
    )


@mcp.tool()
def render_addition_vertical(
    addend_a: str,
    addend_b: str,
    include_verification: bool = False,
) -> str:
    """非负整数加法竖式。"""
    return mcp_svg_text_to_tool_output(
        build_addition_vertical_svg(addend_a, addend_b, include_verification=include_verification)
    )


@mcp.tool()
def render_subtraction_vertical(
    minuend: str,
    subtrahend: str,
    include_verification: bool = False,
) -> str:
    """非负整数减法竖式（被减数须 ≥ 减数）。"""
    return mcp_svg_text_to_tool_output(
        build_subtraction_vertical_svg(minuend, subtrahend, include_verification=include_verification)
    )


@mcp.tool()
def render_multiplication_vertical(
    factor_a: str,
    factor_b: str,
    include_verification: bool = False,
) -> str:
    """乘法竖式（支持小数因子）。"""
    return mcp_svg_text_to_tool_output(
        build_multiplication_vertical_svg(factor_a, factor_b, include_verification=include_verification)
    )


@mcp.tool()
def render_integer_division_vertical(
    dividend: str,
    divisor: str,
    include_verification: bool = False,
) -> str:
    """非负整数除法竖式，商为整数并保留余数（教材长除）。"""
    return mcp_svg_text_to_tool_output(
        build_integer_division_vertical_svg(dividend, divisor, include_verification=include_verification)
    )


def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


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
