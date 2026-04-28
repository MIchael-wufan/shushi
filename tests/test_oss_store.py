"""oss_store：HTML 片段与 raw 模式；oss_img 在未配置 OSS 时抛 OSError。"""
import os
import unittest

from division_vertical_mcp.oss_store import (
    ENV_OSS_ACCESS_KEY_ID,
    ENV_OSS_ACCESS_KEY_SECRET,
    ENV_OSS_BUCKET,
    ENV_OSS_ENDPOINT,
    ENV_OSS_PUBLIC_BASE_URL,
    ENV_SVG_OUTPUT_MODE,
    format_svg_oss_img_html,
    mcp_svg_text_to_tool_output,
)

_OSS_ENV_KEYS = (
    ENV_OSS_ACCESS_KEY_ID,
    ENV_OSS_ACCESS_KEY_SECRET,
    ENV_OSS_ENDPOINT,
    ENV_OSS_BUCKET,
    ENV_OSS_PUBLIC_BASE_URL,
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
    "OSS_ENDPOINT",
    "OSS_BUCKET",
    "OSS_PUBLIC_BASE_URL",
)


class TestOssStoreFormat(unittest.TestCase):
    def test_format_svg_oss_img_html(self) -> None:
        s = format_svg_oss_img_html("https://oss.example.com/a.svg", width_px=120)
        self.assertIn('src="https://oss.example.com/a.svg"', s)
        self.assertIn('width="120px"', s)
        self.assertTrue(s.startswith("<br><img "))

    def test_format_escapes_quotes_in_url(self) -> None:
        s = format_svg_oss_img_html('https://x.com/a"b.svg', width_px=100)
        self.assertNotIn('"b.svg', s.split("src=")[1][:80])
        self.assertIn("&quot;", s)


class TestMcpOutputRaw(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.get(ENV_SVG_OUTPUT_MODE)

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop(ENV_SVG_OUTPUT_MODE, None)
        else:
            os.environ[ENV_SVG_OUTPUT_MODE] = self._old

    def test_raw_svg_unchanged(self) -> None:
        os.environ[ENV_SVG_OUTPUT_MODE] = "raw_svg"
        svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        self.assertEqual(mcp_svg_text_to_tool_output(svg), svg)


class TestMcpOutputDefaultOss(unittest.TestCase):
    """未设置环境变量时默认为 oss_img；未配置 OSS 环境变量则抛 OSError。"""

    def setUp(self) -> None:
        self._old_mode = os.environ.get(ENV_SVG_OUTPUT_MODE)
        self._saved_oss: dict[str, str | None] = {}
        for k in _OSS_ENV_KEYS:
            self._saved_oss[k] = os.environ.pop(k, None)
        os.environ.pop(ENV_SVG_OUTPUT_MODE, None)

    def tearDown(self) -> None:
        for k, v in self._saved_oss.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if self._old_mode is None:
            os.environ.pop(ENV_SVG_OUTPUT_MODE, None)
        else:
            os.environ[ENV_SVG_OUTPUT_MODE] = self._old_mode

    def test_default_raises_when_oss_not_configured(self) -> None:
        svg = "<svg></svg>"
        with self.assertRaises(OSError) as ctx:
            mcp_svg_text_to_tool_output(svg)
        self.assertIn("OSS", str(ctx.exception))
