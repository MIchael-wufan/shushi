"""
公司 OSS 上传与 MCP 结果封装。

阿里云 OSS：配置环境变量后 ``upload_svg_get_public_url`` 会上传 SVG 并返回公网 URL。
默认 MCP 输出为含 ``<img>`` 的 HTML；亦可 ``raw_svg`` 或 ``oss_url``（仅 URL）。
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Final
from urllib.parse import quote

import oss2
from dotenv import load_dotenv

# 从项目根目录加载 .env（文件已在 .gitignore，勿把密钥提交到 Git）
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

# ---------------------------------------------------------------------------
# 环境变量（与 server 共用约定）
# ---------------------------------------------------------------------------
# 可选值，大小写不敏感:
#   oss_img    — 默认。将 SVG 上传至 OSS 后，返回可嵌入的 HTML 片段（见 `format_svg_oss_img_html`）
#   oss_url    — 上传后仅返回公网 URL 字符串（无 <img>）
#   raw_svg    — 工具直接返回 UTF-8 完整 SVG 字符串
ENV_SVG_OUTPUT_MODE: Final = "DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE"
# img 标签的 width，默认 120；单位在 HTML 中写为「120px」
ENV_SVG_IMG_WIDTH: Final = "DIVISION_VERTICAL_MCP_SVG_IMG_WIDTH"

# 阿里云 OSS（与 README / docs/OSS_UPLOAD_GUIDE.md 一致；密钥勿写入仓库）
ENV_OSS_ACCESS_KEY_ID: Final = "DIVISION_VERTICAL_OSS_ACCESS_KEY_ID"
ENV_OSS_ACCESS_KEY_SECRET: Final = "DIVISION_VERTICAL_OSS_ACCESS_KEY_SECRET"
ENV_OSS_ENDPOINT: Final = "DIVISION_VERTICAL_OSS_ENDPOINT"
ENV_OSS_BUCKET: Final = "DIVISION_VERTICAL_OSS_BUCKET"
# 浏览器 / <img> 使用的公网基址，无尾部斜杠亦可，例如 https://bucket.oss-cn-beijing.aliyuncs.com
ENV_OSS_PUBLIC_BASE_URL: Final = "DIVISION_VERTICAL_OSS_PUBLIC_BASE_URL"


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


def _env_first(*names: str) -> str | None:
    for name in names:
        v = os.environ.get(name)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _oss_public_url(public_base: str, object_key: str) -> str:
    base = public_base.rstrip("/")
    # 保留路径分隔符，对其余需编码的字符做百分号编码
    path = quote(object_key, safe="/")
    return f"{base}/{path}"


def upload_svg_get_public_url(
    svg_text: str, *, object_key: str | None = None, content_type: str = "image/svg+xml"
) -> str:
    """
    将 **UTF-8 完整 SVG 文档** 上传阿里云 OSS，返回**公网可直接 GET** 的 URL。

    需在环境中配置（也可用无前缀 ``OSS_*`` 同名变量）：

    - ``DIVISION_VERTICAL_OSS_ACCESS_KEY_ID`` / ``OSS_ACCESS_KEY_ID``
    - ``DIVISION_VERTICAL_OSS_ACCESS_KEY_SECRET`` / ``OSS_ACCESS_KEY_SECRET``
    - ``DIVISION_VERTICAL_OSS_ENDPOINT`` / ``OSS_ENDPOINT`` — SDK 访问地址（内网 ECS 可用 internal endpoint）
    - ``DIVISION_VERTICAL_OSS_BUCKET`` / ``OSS_BUCKET``
    - ``DIVISION_VERTICAL_OSS_PUBLIC_BASE_URL`` / ``OSS_PUBLIC_BASE_URL`` — 返回给前端的公网基址，例如
      ``https://apolo-image-test.oss-cn-beijing.aliyuncs.com``
    """
    if object_key is None:
        object_key = _default_object_key()

    access_key_id = _env_first(ENV_OSS_ACCESS_KEY_ID, "OSS_ACCESS_KEY_ID")
    access_key_secret = _env_first(ENV_OSS_ACCESS_KEY_SECRET, "OSS_ACCESS_KEY_SECRET")
    endpoint = _env_first(ENV_OSS_ENDPOINT, "OSS_ENDPOINT")
    bucket_name = _env_first(ENV_OSS_BUCKET, "OSS_BUCKET")
    public_base = _env_first(ENV_OSS_PUBLIC_BASE_URL, "OSS_PUBLIC_BASE_URL")

    required = {
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "endpoint": endpoint,
        "bucket": bucket_name,
        "public_base": public_base,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise OSError(
            "阿里云 OSS 环境变量不完整（缺少: "
            + ", ".join(missing)
            + "）。请设置 DIVISION_VERTICAL_OSS_* 或 OSS_*；"
            f"或设置 {ENV_SVG_OUTPUT_MODE}=raw_svg 跳过上传。"
        )

    ct = content_type
    if "charset" not in ct.lower():
        ct = f"{content_type}; charset=utf-8"

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    body = svg_text.encode("utf-8")
    bucket.put_object(object_key, body, headers={"Content-Type": ct})

    return _oss_public_url(public_base, object_key)


# ---------------------------------------------------------------------------


def mcp_svg_text_to_tool_output(svg: str) -> str:
    """
    MCP 各工具在得到 SVG 字符串后统一经此函数再返回给客户端。

    - ``raw_svg``：原样返回 ``svg``。
    - ``oss_img``：调用 ``upload_svg_get_public_url`` 后，返回 ``format_svg_oss_img_html``。
    - ``oss_url``：上传后仅返回公网 URL 字符串。
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
    if mode in ("oss_url", "url"):
        key = _default_object_key()
        url = upload_svg_get_public_url(svg, object_key=key)
        if not _looks_like_url(url):
            raise ValueError(
                f"upload_svg_get_public_url 应返回以 http:// 或 https:// 开头的 URL，收到: {url!r}"
            )
        return url
    raise ValueError(
        f"未知 {ENV_SVG_OUTPUT_MODE}={mode!r}；"
        f"请使用 raw_svg、oss_img 或 oss_url（简写 raw / oss_url）"
    )


def _looks_like_url(s: str) -> bool:
    s = s.strip()
    return s.startswith("http://") or s.startswith("https://")
