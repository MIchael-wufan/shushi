"""
公司 OSS 上传与 MCP 结果封装。

`upload_svg_get_public_url` 由你方在部署时接入贵司对象存储后实现。默认输出为上传后的 HTML 片段；
若仅需 SVG 文本，可设置环境变量 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg``。
"""
from __future__ import annotations

import os
import uuid
from typing import Final

# ---------------------------------------------------------------------------
# 环境变量（与 server 共用约定）
# ---------------------------------------------------------------------------
# 可选值，大小写不敏感:
#   oss_img    — 默认。将 SVG 上传至 OSS 后，返回可嵌入的 HTML 片段（见 `format_svg_oss_img_html`）
#   raw_svg    — 工具直接返回 UTF-8 完整 SVG 字符串
ENV_SVG_OUTPUT_MODE: Final = "DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE"
# img 标签的 width，默认 120；单位在 HTML 中写为「120px」
ENV_SVG_IMG_WIDTH: Final = "DIVISION_VERTICAL_MCP_SVG_IMG_WIDTH"


def get_svg_output_mode() -> str:
    v = os.environ.get(ENV_SVG_OUTPUT_MODE, "oss_img")
    return v.strip().lower() or "oss_img"


def get_svg_img_width_px() -> int:
    s = os.environ.get(ENV_SVG_IMG_WIDTH, "120")
    try:
        w = int(s)
        return w if w > 0 else 120
    except ValueError:
        return 120


def format_svg_oss_img_html(public_url: str, *, width_px: int | None = None) -> str:
    """
    将公网可访问的 SVG 资源 URL 格式化为 MCP 返回的 HTML 片段，例如::

        <br><img src="https://oss.example.com/bucket/foo.svg" width="120px"><br>

    ``public_url`` 中的 ``"`` 会被转义，避免破坏属性。

    说明：Confluence/部分 Wiki 的宏若需要纯 URL，可再自行从 img 中解析或改为仅返回 URL。
    """
    w = width_px if width_px is not None else get_svg_img_width_px()
    # 属性值用双引号，并对引号作 HTML 转义
    safe = (
        public_url.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<br><img src="{safe}" width="{w}px"><br>'


def _default_object_key() -> str:
    """未指定 object key 时生成唯一路径（可按公司规范改前缀）。"""
    return f"division-vertical-mcp/{uuid.uuid4().hex}.svg"


# ---------------------------------------------------------------------------
# 部署时请在本函数中接入贵司 OSS（需实现）
# ---------------------------------------------------------------------------
def upload_svg_get_public_url(
    svg_text: str, *, object_key: str | None = None, content_type: str = "image/svg+xml"
) -> str:
    """
    将 **UTF-8 完整 SVG 文档** 上传到公司 OSS，返回**公网可直接 GET** 的 URL
   （浏览器或 ``<img>`` 可加载）。

    参数
    ----
    svg_text
        要上传的 SVG 源文本（建议含 ``<svg>`` 根元素）。
    object_key
        对象键/路径；默认 ``_default_object_key()``，以免覆盖。
    content_type
        建议 ``image/svg+xml`` 或带 ``charset=utf-8``。

    返回
    ----
    以 ``http://`` 或 ``https://`` 开头的资源 URL 字符串；供 ``format_svg_oss_img_html`` 使用。

    未实现
    ------
    当前默认 **抛出** ``NotImplementedError``。在 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=oss_img`` 时，
    必须在部署环境实现本函数，或将输出模式设回 ``raw_svg``。

    实现提示
    --------
    常见：阿里云 OSS、华为 OBS、MinIO、AWS S3、自研网关等。上传后返回带签名或
    公开读桶的**稳定 URL**；注意跨域 CORS 若需前端直接 <img> 使用。
    """
    raise NotImplementedError(
        "在 division_vertical_mcp.oss_store.upload_svg_get_public_url 中接入公司 OSS 后，"
        "本函数应返回可访问的 SVG 资源 URL；"
        f"或设置 {ENV_SVG_OUTPUT_MODE}=raw_svg 不走上传。"
    )


# ---------------------------------------------------------------------------


def mcp_svg_text_to_tool_output(svg: str) -> str:
    """
    MCP 各工具在得到 SVG 字符串后统一经此函数再返回给客户端。

    - ``raw_svg``：原样返回 ``svg``。
    - ``oss_img``：调用 ``upload_svg_get_public_url`` 后，返回 ``format_svg_oss_img_html``。
    """
    mode = get_svg_output_mode()
    if mode in ("raw_svg", "raw", "svg"):
        return svg
    if mode in ("oss_img", "oss", "img", "html_img"):
        key = _default_object_key()
        url = upload_svg_get_public_url(svg, object_key=key)
        if not _looks_like_url(url):
            raise ValueError(
                f"upload_svg_get_public_url 应返回以 http:// 或 https:// 开头的 URL，收到: {url!r}"
            )
        return format_svg_oss_img_html(url)
    raise ValueError(
        f"未知 {ENV_SVG_OUTPUT_MODE}={mode!r}；"
        f"请使用 raw_svg 或 oss_img（或简写 raw/oss/img）"
    )


def _looks_like_url(s: str) -> bool:
    s = s.strip()
    return s.startswith("http://") or s.startswith("https://")
