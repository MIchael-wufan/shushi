from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .compose import (
    build_addition_vertical_svg,
    build_combined_svg,
    build_integer_division_vertical_svg,
    build_multiplication_vertical_svg,
    build_subtraction_vertical_svg,
)
from .oss_store import mcp_svg_text_to_tool_output

mcp = FastMCP("division-vertical")


@mcp.tool()
def render_division_vertical(
    dividend: str,
    divisor: str,
    include_verification: bool = False,
    retain_decimal_places: int | None = None,
) -> str:
    """
    根据被除数、除数生成教材风格除法竖式图（网格对齐）。
    所有题目共用 `compose.build_combined_svg` 的统一管线：除数小数移位、被除数同步移位、
    分步竖式、除数/被除数红色留痕（前导零、划去的小数点、原小数点位置红点与短划、移位后新小数点等）。
    验算默认关闭；设 include_verification=true 时，在除法竖式下空一行左对齐「验算：」，其下为**数位对齐的乘法竖式**（进位/强调色见 `render_config`）；顶端不再绘制横式算式。
    retain_decimal_places：若给定 n（>=0），横式「=」右侧为四舍五入到 n 位小数的商；竖式在商的小数部分算满 n+1 位后停止（余数为 0 可提前停）。
    返回值：默认（OSS 模式）为含 <img> 的 HTML 片段；设 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`` 时返回完整 UTF-8 SVG。见 ``oss_store`` 与 README。
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
    """
    非负整数加法竖式：数位右对齐、进位可配置色（`render_config.CARRY_BORROW_IN_RED`）、和行去掉多余前导零。
    include_verification=true 时，在下方「验算：」后用减法竖式校验（和 − 第二个加数 = 第一个加数）。
    返回值：默认（OSS 模式）为含 <img> 的 HTML 片段；设 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`` 时返回完整 UTF-8 SVG。见 ``oss_store`` 与 README。
    """
    return mcp_svg_text_to_tool_output(
        build_addition_vertical_svg(
            addend_a, addend_b, include_verification=include_verification
        )
    )


@mcp.tool()
def render_subtraction_vertical(
    minuend: str,
    subtrahend: str,
    include_verification: bool = False,
) -> str:
    """
    非负整数减法竖式（被减数须 ≥ 减数）：红色借位、差去掉多余前导零。
    include_verification=true 时，用加法竖式验算（差 + 减数 = 被减数）。
    返回值：默认（OSS 模式）为含 <img> 的 HTML 片段；设 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`` 时返回完整 UTF-8 SVG。见 ``oss_store`` 与 README。
    """
    return mcp_svg_text_to_tool_output(
        build_subtraction_vertical_svg(
            minuend, subtrahend, include_verification=include_verification
        )
    )


@mcp.tool()
def render_multiplication_vertical(
    factor_a: str,
    factor_b: str,
    include_verification: bool = False,
) -> str:
    """
    乘法竖式（支持小数因子，语义与除法验算乘法一致：内层整数乘、进位色见 `render_config`、积划去多余 0 等）。
    include_verification=true 时，下方「验算：」后接**小数除法竖式**（与 render_division_vertical 同一套逻辑，不含嵌套验算）：一般画「积 ÷ 第二个因数」得第一个因数；若竖式商位与精确商在个别题上不一致，则自动改为「积 ÷ 第一个因数」。
    返回值：默认（OSS 模式）为含 <img> 的 HTML 片段；设 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`` 时返回完整 UTF-8 SVG。见 ``oss_store`` 与 README。
    """
    return mcp_svg_text_to_tool_output(
        build_multiplication_vertical_svg(
            factor_a, factor_b, include_verification=include_verification
        )
    )


@mcp.tool()
def render_integer_division_vertical(
    dividend: str,
    divisor: str,
    include_verification: bool = False,
) -> str:
    """
    非负整数除法竖式，商为整数并保留余数（教材长除）。
    include_verification=true：无余数时仅画「商×除数」乘法竖式；有余数时为乘法竖式 +「积+余数=被除数」加法竖式。
    返回值：默认（OSS 模式）为含 <img> 的 HTML 片段；设 ``DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`` 时返回完整 UTF-8 SVG。见 ``oss_store`` 与 README。
    """
    return mcp_svg_text_to_tool_output(
        build_integer_division_vertical_svg(
            dividend, divisor, include_verification=include_verification
        )
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
