#!/usr/bin/env python3
"""根据 test-3/index.html 的（类型、算式、文件名）重生成 t3-*.svg 与 index.html。

使用当前代码默认（含 `render_config`）。在修改 `svg_render`/`compose`/`render_config`
等绘制逻辑后应重跑，以更新 test-3 中示例。在项目根执行::

    PYTHONPATH=. python3 scripts/generate_test3_from_index.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from division_vertical_mcp.compose import (
    build_addition_vertical_svg,
    build_combined_svg,
    build_integer_division_vertical_svg,
    build_multiplication_vertical_svg,
    build_subtraction_vertical_svg,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-3"
INDEX = OUT / "index.html"

META_PAT = re.compile(
    r'<span class="kind">([^<]+)</span>.*?<span class="expr">([^<]+)</span>.*?<code class="fn">(t3-[^<]+\.svg)</code>',
    re.DOTALL,
)


def _strip_parens(s: str) -> str:
    t = s
    while True:
        u = re.sub(r"（[^）]*）", "", t)
        u = re.sub(r"\([^)]*\)", "", u)
        if u == t:
            break
        t = u
    return t.strip()


def _div_expr(e: str, fn: str) -> tuple[str, str, bool, int | None]:
    verify = "含验算" in e
    if "no_verify" in fn or "_no_verify" in fn:
        verify = False
    r_m = re.search(r"保留\s*(\d)\s*位", e)
    retain: int | None = int(r_m.group(1)) if r_m else None
    core = _strip_parens(e)
    m = re.match(r"^(.+?)\s*÷\s*(.+)$", core)
    if not m:
        raise ValueError(f"无法解析除法: {e!r}")
    return m.group(1).strip(), m.group(2).strip(), verify, retain


def _add_expr(e: str) -> tuple[str, str, bool]:
    verify = "含验算" in e
    core = _strip_parens(e)
    m = re.match(r"^(.+?)\s*\+\s*(.+)$", core)
    if not m:
        raise ValueError(f"无法解析加法: {e!r}")
    return m.group(1).strip(), m.group(2).strip(), verify


def _sub_expr(e: str) -> tuple[str, str, bool]:
    verify = "含验算" in e
    core = _strip_parens(e)
    if "−" in core:
        parts = re.split(r"\s*−\s*", core, maxsplit=1)
    else:
        parts = re.split(r"\s*-\s*", core, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"无法解析减法: {e!r}")
    return parts[0].strip(), parts[1].strip(), verify


def _mul_expr(e: str) -> tuple[str, str, bool]:
    verify = "含验算" in e
    core = _strip_parens(e)
    m = re.match(r"^(.+?)\s*×\s*(.+)$", core)
    if not m:
        raise ValueError(f"无法解析乘法: {e!r}")
    return m.group(1).strip(), m.group(2).strip(), verify


def _idiv_expr(e: str) -> tuple[str, str, bool]:
    verify = "含验算" in e
    core = _strip_parens(e)
    m = re.match(r"^(.+?)\s*÷\s*(.+)$", core)
    if not m:
        raise ValueError(f"无法解析整数除法: {e!r}")
    return m.group(1).strip(), m.group(2).strip(), verify


def _kind_label(zh: str) -> str:
    return {
        "小数除法": "小数除法",
        "加法": "加法",
        "减法": "减法",
        "乘法": "乘法",
        "整数除法": "整数除法",
    }.get(zh, zh)


def _div_label(a: str, b: str, v: bool, r: int | None) -> str:
    t = f"{a} ÷ {b}"
    if r is not None:
        t += f"（保留 {r} 位小数）"
    if v:
        t += "（含验算）"
    return t


def _svg_body_for_embed(svg_text: str) -> str:
    """内嵌到 index 表格单元格：须保留根元素 <svg>…</svg>，否则 <rect>/<text>/<g> 在 HTML
    中无 SVG 父级、浏览器不当作矢量图渲染，只会呈现空白或当作未知标签忽略。
    仅去掉可能存在的 XML 声明。"""
    t = svg_text.strip()
    if t.lower().startswith("<?xml"):
        t = t.split("?>", 1)[-1].strip()
    return t


def main() -> None:
    if not INDEX.is_file():
        raise SystemExit(f"未找到 {INDEX}，请在与 test-3 同级目录下运行本脚本。")
    raw = INDEX.read_text(encoding="utf-8")
    rows: list[tuple[str, str, str]] = META_PAT.findall(raw)
    if len(rows) < 1:
        raise SystemExit("index 中未解析到任何 t3-*.svg 行")

    for kind, expr, name in rows:
        fn = name
        ex = expr.strip()
        if kind == "小数除法":
            a, b, v, r = _div_expr(ex, fn)
            svg = build_combined_svg(
                a, b, include_verification=v, retain_decimal_places=r
            )
        elif kind == "加法":
            a, b, v = _add_expr(ex)
            svg = build_addition_vertical_svg(a, b, include_verification=v)
        elif kind == "减法":
            a, b, v = _sub_expr(ex)
            svg = build_subtraction_vertical_svg(a, b, include_verification=v)
        elif kind == "乘法":
            a, b, v = _mul_expr(ex)
            svg = build_multiplication_vertical_svg(a, b, include_verification=v)
        elif kind == "整数除法":
            a, b, v = _idiv_expr(ex)
            svg = build_integer_division_vertical_svg(a, b, include_verification=v)
        else:
            raise RuntimeError(f"未知类型: {kind}")
        (OUT / fn).write_text(svg, encoding="utf-8")
        print("wrote", "test-3/" + fn)

    tr_parts: list[str] = []
    for kind, expr, fname in rows:
        ex = expr.strip()
        if kind == "小数除法":
            a, b, v, r = _div_expr(ex, fname)
            expr_s = _div_label(a, b, v, r)
        elif kind == "加法":
            a, b, v = _add_expr(ex)
            expr_s = f"{a} + {b}" + ("（含验算）" if v else "")
        elif kind == "减法":
            a, b, v = _sub_expr(ex)
            expr_s = f"{a} − {b}" + ("（含验算）" if v else "")
        elif kind == "乘法":
            a, b, v = _mul_expr(ex)
            expr_s = f"{a} × {b}" + ("（含验算）" if v else "")
        else:
            a, b, v = _idiv_expr(ex)
            expr_s = f"{a} ÷ {b}" + ("（含验算）" if v else "")

        svg_text = (OUT / fname).read_text(encoding="utf-8")
        inner = _svg_body_for_embed(svg_text)
        tr_parts.append(
            "<tr>"
            f'<td class="meta"><span class="kind">{html.escape(_kind_label(kind))}</span><br>'
            f'<span class="expr">{html.escape(expr_s)}</span><br>'
            f'<code class="fn">{html.escape(fname)}</code></td>'
            f'<td class="svg-cell">{inner}</td>'
            "</tr>"
        )

    n = len(rows)
    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>test-3 竖式样例（内嵌 SVG）</title>
  <style>
    :root {{ font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }}
    body {{ margin: 1rem 1.25rem 3rem; background: #fafafa; color: #222; }}
    h1 {{ font-size: 1.35rem; margin-bottom: 0.35rem; }}
    .hint {{ color: #555; font-size: 0.9rem; margin-bottom: 1rem; max-width: 60rem; line-height: 1.5; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1100px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    th, td {{ border: 1px solid #d8d8d8; padding: 10px 12px; vertical-align: top; }}
    th {{ background: #f0f4f8; text-align: left; font-weight: 600; }}
    col.col-expr {{ width: 30%; }}
    col.col-svg {{ width: 70%; }}
    .kind {{ color: #666; font-size: 0.82rem; }}
    .expr {{ font-size: 1.05rem; margin: 0.25rem 0; display: inline-block; }}
    .fn {{ font-size: 0.75rem; color: #888; }}
    .svg-cell svg {{ display: block; max-width: 100%; height: auto; max-height: 400px; margin: 0 auto; }}
  </style>
</head>
<body>
  <h1>test-3 竖式样例总览</h1>
  <p class="hint">
    共 <strong>{n}</strong> 条，两列：算式说明与<strong>内嵌 SVG</strong>。
    除法含验算时，下方已含乘法验算竖式，故不再单独列出与之互逆的乘法题，避免重复。
    本页可单文件转发，收件人无需同目录 <code>.svg</code> 即可查看；同目录 <code>t3-*.svg</code> 亦可单独引用。
  </p>
  <table>
    <colgroup>
      <col class="col-expr" /><col class="col-svg" />
    </colgroup>
    <thead>
      <tr>
        <th scope="col">算式 / 类型 / 文件</th>
        <th scope="col">竖式（SVG）</th>
      </tr>
    </thead>
    <tbody>
{"".join(tr_parts)}
    </tbody>
  </table>
</body>
</html>
"""
    (OUT / "index.html").write_text(index_html, encoding="utf-8")
    print("wrote test-3/index.html")


if __name__ == "__main__":
    main()
