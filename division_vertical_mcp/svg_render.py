from __future__ import annotations

import html
from dataclasses import dataclass

from .decimal_math import ShiftMarks
from .long_division import LongDivisionLayout
from . import render_config
from .school_column_ops import AdditionLayout, SubtractionLayout
from .school_multiply import CarryDigit, DigitRow, SchoolMultiplyLayout


def _remark_color(st: Style) -> str:
    """教学标注色：受 `render_config.REMARKS_IN_RED` 控制；False 时与主文同色。"""
    return st.color_red if render_config.REMARKS_IN_RED else st.color_main


def _carry_borrow_color(st: Style) -> str:
    """进位/借位小号字颜色：受 `render_config.CARRY_BORROW_IN_RED` 控制；False 时与主文同色。"""
    return st.color_red if render_config.CARRY_BORROW_IN_RED else st.color_main


@dataclass
class Style:
    cell_w: float = 13.5
    cell_h: float = 24.0
    gap_bracket: float = 5.0
    color_main: str = "#000000"
    color_red: str = "#e02020"
    font_size: float = 20.0
    row_gap: float = 6.0
    # 数字与符号：Latin Modern Roman（@font-face 见 _latin_modern_defs）
    font_family: str = "'Latin Modern Roman', 'Latin Modern', 'LM Roman 10', serif"


# WiTeX 仓库中的 Latin Modern Roman 10 Regular（GUST 授权，WOFF）
_LM_ROMAN_WOFF = (
    "https://cdn.jsdelivr.net/gh/AndrewBelt/WiTeX@master/fonts/lmroman10-regular.woff"
)


def _latin_modern_defs() -> str:
    """嵌入 @font-face，使未安装本地 Latin Modern 时仍能从 CDN 加载。"""
    return (
        "<defs><style type=\"text/css\"><![CDATA[\n"
        "@font-face {\n"
        "  font-family: 'Latin Modern Roman';\n"
        "  font-style: normal;\n"
        "  font-weight: 400;\n"
        "  font-display: swap;\n"
        f'  src: url("{_LM_ROMAN_WOFF}") format("woff");\n'
        "}\n"
        "]]></style></defs>"
    )


# 所有红色划线共用同一斜率（左上 → 右下），避免宽窄格导致“角度不一”
_STRIKE_SLOPE = 1.14  # dy/dx 越大越陡
_STRIKE_WIDTH = 0.85  # 细线

# 教学红斜线固定为两种（均用 _strike_uniform + 上式斜率）：
# - 小数点：_strike_half_width_dot —— 短划，穿过墨点、尽量不压到两侧数字
# - 数字 0：_strike_zero_half_width —— 略宽于字身、两端稍伸出即可，避免过长


def _strike_y_for_glyph(ch: str, y_row: float, fs: float) -> float:
    """小数点字形相对 dominant-baseline=middle 略偏下，划线中心下移以穿过墨点。"""
    if ch == ".":
        return y_row + fs * 0.11
    return y_row


def _strike_zero_half_width(st: Style) -> float:
    """划在数字 0 上的斜线半宽：以字宽为基准略伸出，比旧版更短、仍穿过椭圆。"""
    digit_w = _char_width("0", st)
    return max(digit_w * 0.34, st.font_size * 0.17)


def _strike_y_for_zero(y_row: float, fs: float) -> float:
    """数字 0 上红斜线中心略上移（相对 dominant-baseline=middle 行）。"""
    return y_row - fs * 0.07


def _recurring_vinculum_svg(cx: float, y_digit_mid: float, st: Style) -> str:
    """循环节：黑色横线置于数字上方，与字顶留缝、不压数字。"""
    fs = st.font_size
    half_w = max(_char_width("0", st) * 0.40, fs * 0.16)
    y_bar = y_digit_mid - fs * 0.54
    return _strike_line(cx - half_w, y_bar, cx + half_w, y_bar, color=st.color_main, width=1.05)


def _strike_half_width_dot(fs: float, dot_col_w: float) -> float:
    """划去小数点的红斜线半长：略短于格宽/字高上界，仍稳定穿过墨点、少侵两侧。"""
    return max(fs * 0.08, min(dot_col_w * 0.40, fs * 0.12))


def _strike_line(x0: float, y0: float, x1: float, y1: float, *, color: str, width: float) -> str:
    return (
        f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
        f'stroke="{color}" stroke-width="{width:.2f}" stroke-linecap="round"/>'
    )


def _strike_uniform(cx: float, cy: float, half_w: float, color: str, *, width: float = _STRIKE_WIDTH) -> str:
    """过 (cx,cy)、半宽 half_w、固定斜率；方向为左上 → 右下（屏幕坐标 y 向下）。"""
    dy = half_w * _STRIKE_SLOPE
    return _strike_line(cx - half_w, cy - dy, cx + half_w, cy + dy, color=color, width=width)


def _text(
    x: float,
    y: float,
    s: str,
    *,
    anchor: str = "middle",
    fs: float | None = None,
    fill: str,
    font_family: str,
) -> str:
    fs = fs or 20.0
    esc = html.escape(s, quote=False)
    ff = font_family.replace("&", "&amp;").replace('"', "&quot;")
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-family="{ff}" font-size="{fs:.1f}" '
        f'fill="{fill}" dominant-baseline="middle">{esc}</text>'
    )


def _char_width(ch: str, st: Style) -> float:
    return st.cell_w * 0.32 if ch == "." else st.cell_w


def _mul_dot_x_hug_left_digit(c_l: int, col_x: list[float], st: Style) -> float:
    """
    乘法竖式：数字列心等距（格宽 cell_w）不变，小数点横坐标紧挨在左侧数字列心右缘（+ 半字宽），
    不占两列中缝、也不按窄点拉宽字距；与 _append_strip_verify_factor_row_parts 等因子行一致。
    """
    if not col_x or c_l < 0 or c_l >= len(col_x):
        return col_x[0] if col_x else 0.0
    return col_x[c_l] + 0.5 * _char_width("0", st)


def _line_char_centers(s: str, st: Style, x_start: float) -> list[float]:
    """与 `render_division_svg` 中逐字心一致：等宽数字、窄小数点，供验算与除法同字距。"""
    out: list[float] = []
    x = x_start
    for ch in s:
        w = _char_width(ch, st)
        x += w * 0.5
        out.append(x)
        x += w * 0.5
    return out


def _col_x_from_known_columns(W: int, known: dict[int, float], margin: float, cw: float) -> list[float]:
    """
    由已知的列号 → 列心 填整表；未知列按相邻等距 cw 内插/外推（全空时退回均匀列心）。
    """
    if W <= 0:
        return []
    known = {c: v for c, v in known.items() if 0 <= c < W and isinstance(v, (int, float))}
    if not known:
        return [margin + (i + 0.5) * cw for i in range(W)]
    col_x: list[float] = [0.0] * W
    for c, v in known.items():
        col_x[c] = v
    keys = sorted(known)
    mink, maxk = min(keys), max(keys)
    for c in range(W):
        if c in known:
            continue
        left = [k for k in keys if k < c]
        right = [k for k in keys if k > c]
        if not left and not right:
            col_x[c] = margin + (c + 0.5) * cw
        elif not left:
            col_x[c] = col_x[mink] - (mink - c) * cw
        elif not right:
            col_x[c] = col_x[maxk] + (c - maxk) * cw
        else:
            lk, rk = max(left), min(right)
            t = 0.0 if rk == lk else (c - lk) / (rk - lk)
            col_x[c] = (1.0 - t) * col_x[lk] + t * col_x[rk]
    return col_x


def _digit_cell_span(dividend_cells: list[str], c0: int, c1: int) -> list[int]:
    return [ci for ci in range(c0, c1 + 1) if dividend_cells[ci] != "."]


def _dvd_cell_index_for_digit_col(dividend_cells: list[str], dcol: int) -> int:
    """数位列 dcol（不含小数点）→ dividend_cells 下标。"""
    di = 0
    for ci, ch in enumerate(dividend_cells):
        if ch == ".":
            continue
        if di == dcol:
            return ci
        di += 1
    raise IndexError("数位列越界")


def _quotient_slots_display(slots: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """竖式商不画前导 0（与横式「去前导零」一致）；商为 0 时只保留最后一位上的 0。"""
    if not slots:
        return []
    for idx, (_c, ch) in enumerate(slots):
        if ch != "0":
            return slots[idx:]
    return [slots[-1]]


def division_subtraction_ink_right_x(
    divisor_cells: list[str],
    dividend_cells: list[str],
    st: Style | None = None,
) -> float:
    """与 `render_division_svg` 中厂内顶横线、各步减法横线之右端 x2 一致（与弯钩/余数无关）。"""
    st = st or Style()
    x_cursor = 20.0
    for ch in divisor_cells:
        w = _char_width(ch, st)
        x_cursor += w / 2
        x_cursor += w / 2
    x_cursor += st.gap_bracket
    dvd_centers: list[float] = []
    for ch in dividend_cells:
        w = _char_width(ch, st)
        x_cursor += w / 2
        dvd_centers.append(x_cursor)
        x_cursor += w / 2
    if not dividend_cells or not dvd_centers:
        return x_cursor
    return dvd_centers[-1] + _char_width(dividend_cells[-1], st) * 0.48


def render_division_svg(
    *,
    divisor_cells: list[str],
    dividend_cells: list[str],
    marks: ShiftMarks,
    layout: LongDivisionLayout,
    horizontal_line: str = "",
    st: Style | None = None,
) -> str:
    """按 `ShiftMarks` + `LongDivisionLayout` 绘制竖式；默认不画顶端横式（`horizontal_line` 为空即可）。
    首步不重复画部分被除数行；非末步不画「仅余数」行（下一步 partial 已表示落位后数）。
    业务侧请只通过 `compose.build_combined_svg` 生成参数，勿为单题手写 marks/layout。"""
    st = st or Style()
    fs = st.font_size
    c_main = st.color_main
    c_red = _remark_color(st)

    w_left = sum(_char_width(c, st) for c in divisor_cells) + st.gap_bracket + st.cell_w * 0.28
    w_right = sum(_char_width(c, st) for c in dividend_cells)
    w_body = w_left + w_right + 32
    total_w = w_body

    # —— 纵向网格（自上而下；无顶端横式）——
    # 被除数、除数共行：基线
    y_main = 48.0
    # 厂字顶横线：在数字中心线之上，与数字顶留足空隙
    roof_y = y_main - fs * 0.62
    # 商：紧挨顶横线上方
    y_quotient = roof_y - fs * 0.48 - 5.0
    # 第一步减数行基线（与主行明确分层）
    y_sub_base = y_main + fs * 1.08
    # 横线压在数字中间 → 改为「数字整行之下」
    gap_digit_to_rule = fs * 0.50
    gap_rule_to_next = fs * 0.64
    y_hook_bottom = y_main + fs * 0.34

    # 每步：乘积 → 横线 →（末步）余数；首步不单独画「部分被除数」（与厂内首行重复）；
    # 非末步不画「仅余数」行（下一步开头的部分被除数已含落位数字，如 12→125）。
    row_sub = fs * 1.02

    n_steps = len(layout.steps)
    # 高度必须与绘制循环一致：旧版用「每步一整行 row_sub + 乘积到横线」估算，会把画布底部垫得过高，
    # 组合图里主竖式底到「验算：」之间出现大块空白。
    ink_bottom_y = y_sub_base
    for si, _step in enumerate(layout.steps):
        if si > 0:
            ink_bottom_y += row_sub
        line_y = ink_bottom_y + gap_digit_to_rule
        ink_bottom_y = line_y + gap_rule_to_next
        if si == n_steps - 1:
            ink_bottom_y += row_sub * 0.92
    if not layout.steps:
        ink_bottom_y = y_sub_base + row_sub * 0.92
    bottom_pad = fs * 0.42 + 8.0
    total_h = max(ink_bottom_y + bottom_pad, y_hook_bottom + 24.0, fs * 3.0)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.1f}" height="{total_h:.1f}" '
        f'viewBox="0 0 {total_w:.1f} {total_h:.1f}">'
    )
    parts.append('<rect width="100%" height="100%" fill="white"/>')
    parts.append(_latin_modern_defs())
    ff = st.font_family
    if horizontal_line and horizontal_line.strip():
        parts.append(
            _text(total_w / 2, 20.0, horizontal_line, anchor="middle", fs=fs + 2, fill=c_main, font_family=ff)
        )

    x_cursor = 20.0
    div_centers: list[float] = []
    for ch in divisor_cells:
        w = _char_width(ch, st)
        x_cursor += w / 2
        div_centers.append(x_cursor)
        x_cursor += w / 2
    bracket_x0 = x_cursor + st.gap_bracket * 0.15
    x_cursor += st.gap_bracket
    dvd_centers: list[float] = []
    for ch in dividend_cells:
        w = _char_width(ch, st)
        x_cursor += w / 2
        dvd_centers.append(x_cursor)
        x_cursor += w / 2

    q_slots_draw = _quotient_slots_display(layout.quotient_slots)
    last_int_col: int | None = None
    for col, ch in q_slots_draw:
        if 0 <= col < len(dvd_centers):
            parts.append(_text(dvd_centers[col], y_quotient, ch, fs=fs, fill=c_main, font_family=ff))
            last_int_col = col
    if layout.has_quotient_decimal_point and layout.quotient_frac_slots:
        fc0 = layout.quotient_frac_slots[0][0]
        if (
            marks.dividend_new_decimal_cell_index is not None
            and 0 <= marks.dividend_new_decimal_cell_index < len(dvd_centers)
        ):
            xdot = dvd_centers[marks.dividend_new_decimal_cell_index]
        elif last_int_col is not None and 0 <= fc0 < len(dvd_centers):
            xdot = (dvd_centers[last_int_col] + dvd_centers[fc0]) / 2.0
        else:
            xdot = dvd_centers[fc0] if 0 <= fc0 < len(dvd_centers) else dvd_centers[-1]
        parts.append(_text(xdot, y_quotient, ".", fs=fs, fill=c_main, font_family=ff))
        rec_i = getattr(layout, "quotient_recurring_dot_frac_slot_index", None)
        for fi, (col, ch) in enumerate(layout.quotient_frac_slots):
            if 0 <= col < len(dvd_centers):
                cx = dvd_centers[col]
                parts.append(_text(cx, y_quotient, ch, fs=fs, fill=c_main, font_family=ff))
                if rec_i is not None and fi == rec_i:
                    parts.append(_recurring_vinculum_svg(cx, y_quotient, st))

    for idx, ch in enumerate(divisor_cells):
        parts.append(_text(div_centers[idx], y_main, ch, fs=fs, fill=c_main, font_family=ff))
    ext_red = frozenset(getattr(marks, "dividend_extension_red_digit_cells", ()) or ())
    for idx, ch in enumerate(dividend_cells):
        cx = dvd_centers[idx]
        is_new_red_dot = (
            marks.dividend_new_decimal_cell_index is not None
            and idx == marks.dividend_new_decimal_cell_index
            and ch == "."
        )
        is_ext_red_zero = idx in ext_red and ch == "0"
        tfill = c_red if (is_new_red_dot or is_ext_red_zero) else c_main
        parts.append(_text(cx, y_main, ch, fs=fs, fill=tfill, font_family=ff))
        if marks.dividend_dot_strike and ch == ".":
            cy_s = _strike_y_for_glyph(".", y_main, fs)
            hw = _strike_half_width_dot(fs, _char_width(".", st))
            parts.append(_strike_uniform(cx, cy_s, hw, c_red))
    for _zi in getattr(marks, "dividend_prefix_zero_strike_cells", []) or []:
        if 0 <= _zi < len(dividend_cells) and dividend_cells[_zi] == "0":
            cx = dvd_centers[_zi]
            cy_s = _strike_y_for_zero(y_main, fs)
            hw = _strike_zero_half_width(st)
            parts.append(_strike_uniform(cx, cy_s, hw, c_red))
    for _di in getattr(marks, "dividend_prefix_dot_strike_cells", []) or []:
        if 0 <= _di < len(dividend_cells) and dividend_cells[_di] == ".":
            cx = dvd_centers[_di]
            cy_s = _strike_y_for_glyph(".", y_main, fs)
            hw = _strike_half_width_dot(fs, _char_width(".", st))
            parts.append(_strike_uniform(cx, cy_s, hw, c_red))
    if marks.dividend_old_decimal_gap_after_digit is not None:
        g = marks.dividend_old_decimal_gap_after_digit
        try:
            ci0 = _dvd_cell_index_for_digit_col(dividend_cells, g)
            ci1 = _dvd_cell_index_for_digit_col(dividend_cells, g + 1)
            xmid = (dvd_centers[ci0] + dvd_centers[ci1]) / 2.0
            # 原小数点：画在两数字正中、与行内小数点同高；仅短红斜线划去（不再画两数字间的长斜线）
            parts.append(_text(xmid, y_main, ".", fs=fs, fill=c_red, font_family=ff))
            cy_dot = _strike_y_for_glyph(".", y_main, fs)
            hw_dot = _strike_half_width_dot(fs, _char_width(".", st))
            parts.append(_strike_uniform(xmid, cy_dot, hw_dot, c_red))
        except IndexError:
            pass
    for si in range(min(marks.divisor_leading_zero_strikes, len(div_centers))):
        cx = div_centers[si]
        ch = divisor_cells[si]
        if ch != "0":
            continue
        hw = _strike_zero_half_width(st)
        parts.append(_strike_uniform(cx, _strike_y_for_zero(y_main, fs), hw, c_red))
    if marks.divisor_dot_strike:
        for idx, ch in enumerate(divisor_cells):
            if ch != ".":
                continue
            cx = div_centers[idx]
            cy_s = _strike_y_for_glyph(".", y_main, fs)
            hw = _strike_half_width_dot(fs, _char_width(".", st))
            parts.append(_strike_uniform(cx, cy_s, hw, c_red))
            break
    frac_n = getattr(marks, "divisor_fractional_leading_zero_strikes", 0) or 0
    if frac_n > 0 and marks.divisor_dot_strike:
        try:
            dot_i = next(i for i, ch in enumerate(divisor_cells) if ch == ".")
        except StopIteration:
            dot_i = -1
        if dot_i >= 0:
            for j in range(frac_n):
                idx = dot_i + 1 + j
                if idx < len(divisor_cells) and divisor_cells[idx] == "0":
                    cx = div_centers[idx]
                    hw = _strike_zero_half_width(st)
                    parts.append(_strike_uniform(cx, _strike_y_for_zero(y_main, fs), hw, c_red))

    # 厂字头与被除数区各条减法横线同宽（右端与顶横线对齐）
    first_dvd_x = dvd_centers[0] - _char_width(dividend_cells[0], st) * 0.48
    last_dvd_x = dvd_centers[-1] + _char_width(dividend_cells[-1], st) * 0.48
    arc_x = bracket_x0
    # 光滑连接弧底 → 顶横线左端
    parts.append(
        f'<path d="M {arc_x:.2f} {y_hook_bottom:.2f} '
        f"Q {arc_x + fs * 0.35:.2f} {roof_y + fs * 0.28:.2f} {first_dvd_x:.2f} {roof_y:.2f}\" "
        f'fill="none" stroke="{c_main}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    parts.append(
        f'<line x1="{first_dvd_x:.2f}" y1="{roof_y:.2f}" x2="{last_dvd_x:.2f}" y2="{roof_y:.2f}" '
        f'stroke="{c_main}" stroke-width="1.75"/>'
    )

    def _draw_number_row(y_row: float, s: str, span: list[int]) -> None:
        digits = list(s)
        ln = len(digits)
        for j, dch in enumerate(digits):
            idx = len(span) - ln + j
            if 0 <= idx < len(span):
                col = span[idx]
                parts.append(_text(dvd_centers[col], y_row, dch, fs=fs, fill=c_main, font_family=ff))

    cur_y = y_sub_base
    for si, step in enumerate(layout.steps):
        end_c = step.partial_end_col
        span_m = _digit_cell_span(dividend_cells, step.partial_start_col, end_c)

        if si > 0:
            _draw_number_row(cur_y, str(step.partial), span_m)
            cur_y += row_sub
        _draw_number_row(cur_y, str(step.product), span_m)
        line_y = cur_y + gap_digit_to_rule
        parts.append(
            f'<line x1="{first_dvd_x:.2f}" y1="{line_y:.2f}" x2="{last_dvd_x:.2f}" y2="{line_y:.2f}" '
            f'stroke="{c_main}" stroke-width="1.75"/>'
        )
        cur_y = line_y + gap_rule_to_next
        ra = step.remainder_after
        rs = str(ra)
        r_start = max(0, end_c - len(rs) + 1)
        span_r = _digit_cell_span(dividend_cells, r_start, end_c)
        if si == n_steps - 1:
            _draw_number_row(cur_y, rs, span_r)
            cur_y += row_sub * 0.92

    # 余数已在各步 remainder_after 中画出；无步骤时补画末余数
    if not layout.steps:
        rem = str(layout.final_remainder)
        if rem != "0":
            end_c = len(dvd_centers) - 1
            for j, dch in enumerate(rem):
                col = end_c - len(rem) + 1 + j
                if 0 <= col < len(dvd_centers):
                    parts.append(_text(dvd_centers[col], cur_y, dch, fs=fs, fill=c_main, font_family=ff))
        else:
            zero_col = len(dvd_centers) - 1
            if 0 <= zero_col < len(dvd_centers):
                parts.append(_text(dvd_centers[zero_col], cur_y, "0", fs=fs, fill=c_main, font_family=ff))

    parts.append("</svg>")
    return "\n".join(parts)


def _mul_text_right(s: str, right: float, y: float, st: Style, parts: list[str], ff: str, fs: float, fill: str) -> None:
    x = right
    for ch in reversed(s):
        w = _char_width(ch, st)
        x -= w
        parts.append(_text(x + w / 2, y, ch, fs=fs, fill=fill, font_family=ff))


def _mul_digit_row_cells(
    row: DigitRow,
    col_x: list[float],
    y: float,
    st: Style,
    parts: list[str],
    ff: str,
    fs: float,
    fill: str,
    *,
    col_shift: int = 0,
) -> None:
    for col, ch in sorted(row.cells.items()):
        c = col + col_shift
        if 0 <= c < len(col_x):
            parts.append(_text(col_x[c], y, ch, fs=fs, fill=fill, font_family=ff))


def _mul_carry_y_between_partial_rows(y_row_upper: float, y_row_lower: float, fs: float) -> float:
    """从第二行部分积起：进位落在上一行部分积与本行部分积之间（如 175 与 70 之间）。"""
    band = y_row_lower - y_row_upper
    if band <= fs * 0.55:
        return y_row_upper + fs * 0.20
    d = max(fs * 0.50, min(fs * 0.76, band * 0.52))
    yc = y_row_lower - d
    lo = y_row_upper + fs * 0.24
    hi = y_row_lower - fs * 0.40
    return max(lo, min(yc, hi))


def _mul_carry_y_between_rule2_and_product(line2_y: float, prod_y: float, fs: float) -> float:
    """求和进位：落在第二条横线与积行之间。"""
    band = prod_y - line2_y
    if band <= fs * 0.38:
        return line2_y + fs * 0.14
    d = max(fs * 0.60, min(fs * 0.88, band * 0.56))
    yc = prod_y - d
    lo = line2_y + fs * 0.20
    hi = prod_y - fs * 0.42
    return max(lo, min(yc, hi))


def _mul_draw_carries(
    carries: list,
    col_x: list[float],
    y_carry_row: float,
    st: Style,
    parts: list[str],
    ff: str,
    fs: float,
    *,
    cw: float | None = None,
    y_center_direct: float | None = None,
    col_shift: int = 0,
) -> None:
    """进位/借位数字：小号字，列心偏右作「右上」；是否绘制见 `render_config.SHOW_CARRY_BORROW_DIGITS`，色见 `CARRY_BORROW_IN_RED`。

    `y_center_direct`：若给定，则红字垂直中心用该值（与 `_text` 的 dominant-baseline=middle 一致），
    用于第一行部分积进位落在乘号下第一条横线上；否则在 `y_carry_row` 基础上略上移。

    `col_shift`：与验算乘法内层列整体右移一致（如 0.016×3 真积列与部分积同列对齐）。
    """
    if not render_config.SHOW_CARRY_BORROW_DIGITS:
        return
    fs_s = fs * 0.58
    cell = cw or st.cell_w
    dx = cell * 0.34
    dy = fs * 0.26
    for c in carries:
        cc = c.col + col_shift
        if cc < 0 or cc >= len(col_x):
            continue
        x_draw = col_x[cc] + dx
        if y_center_direct is not None:
            y_draw = y_center_direct
        else:
            y_draw = y_carry_row - dy
        parts.append(
            _text(
                x_draw, y_draw, c.ch, fs=fs_s, fill=_carry_borrow_color(st), font_family=ff
            )
        )


def _mul_second_rule_line_x1_x2(
    *,
    col_x: list[float],
    cw: float,
    fs: float,
    rule_x1: float,
    rule_x2: float,
    partial_rows: list[tuple[list[CarryDigit], DigitRow]],
    product_col_range: tuple[int, int] | None = None,
    extra_digit_cols: list[int] | None = None,
    layout_col_shift: int = 0,
) -> tuple[float, float]:
    """部分积块下方的第二条横线：左右端包住所有部分积数字、进位（及可选的积占列、甩下列）。"""
    fs_carry = fs * 0.58
    carry_hw = max(fs_carry * 0.34, cw * 0.14)

    x1_cands: list[float] = [rule_x1]
    x2_cands: list[float] = [rule_x2]

    for carries, prow in partial_rows:
        for c, _ch in prow.cells.items():
            cc = c + layout_col_shift
            if 0 <= cc < len(col_x):
                x1_cands.append(col_x[cc] - cw * 0.5)
                x2_cands.append(col_x[cc] + cw * 0.5)
        for c in carries:
            cc = c.col + layout_col_shift
            if cc < 0 or cc >= len(col_x):
                continue
            cx = col_x[cc] + cw * 0.34
            x1_cands.append(cx - carry_hw)
            x2_cands.append(cx + carry_hw)

    if extra_digit_cols:
        for c in extra_digit_cols:
            if 0 <= c < len(col_x):
                x1_cands.append(col_x[c] - cw * 0.5)
                x2_cands.append(col_x[c] + cw * 0.5)

    if product_col_range is not None:
        cl, cr = product_col_range
        if 0 <= cl < len(col_x) and 0 <= cr < len(col_x):
            x1_cands.append(col_x[cl] - cw * 0.5)
            x2_cands.append(col_x[cr] + cw * 0.5)

    x1 = min(x1_cands)
    x2 = max(x2_cands)
    x1 = max(2.0, x1)
    if x2 <= x1:
        return rule_x1, rule_x2
    return x1, x2


def _mul_row_text_width(s: str, st: Style) -> float:
    return sum(_char_width(c, st) for c in s)


def _mul_should_strike_dot_after_frac_trailing_zeros(
    product_display: str, dot_i: int, strike_j: list[int]
) -> bool:
    """小数段全是将被划去的尾随 0 时，小数点已无意义，应一并划去。"""
    if not strike_j:
        return False
    frac = product_display[dot_i + 1 :]
    return bool(frac) and all(ch == "0" for ch in frac)


def _mul_strike_trailing_fractional_zeros(
    product_display: str, right: float, y: float, st: Style, parts: list[str], ff: str, fs: float, c_red: str
) -> None:
    """小数点后末尾无效 0：与除法竖式相同的红斜线（不划乘数上的 0）。"""
    if "." not in product_display:
        return
    dot_i = product_display.index(".")
    strike_j: list[int] = []
    for j in range(len(product_display) - 1, dot_i, -1):
        if product_display[j] == "0":
            strike_j.append(j)
        else:
            break
    if not strike_j:
        return
    x = right
    centers: dict[int, float] = {}
    for j in range(len(product_display) - 1, -1, -1):
        ch = product_display[j]
        w = _char_width(ch, st)
        x -= w
        centers[j] = x + w / 2.0
    for j in strike_j:
        cx = centers.get(j)
        if cx is None:
            continue
        hw = _strike_zero_half_width(st)
        parts.append(_strike_uniform(cx, _strike_y_for_zero(y, fs), hw, c_red))
    if _mul_should_strike_dot_after_frac_trailing_zeros(product_display, dot_i, strike_j):
        cx_dot = centers.get(dot_i)
        if cx_dot is not None:
            cy_s = _strike_y_for_glyph(".", y, fs)
            hw_dot = _strike_half_width_dot(fs, _char_width(".", st))
            parts.append(_strike_uniform(cx_dot, cy_s, hw_dot, c_red))


def _strip_verify_product_cols_from_sum(
    sum_row: DigitRow,
    product_display: str,
    dgrid,
) -> tuple[int, int] | None:
    """
    商尾零 strip 验算：真积的全体数字（按横式顺序连接）末段与内层和行数字串一致时，
    将各数字与和行同列对齐；前导多出的数字（如 0.48 的整数 0）占和行最左列左侧连续列。
    不依赖小数位 hack（nd_ip==1 等），避免 12.6/126、0.48/48 等分支分叉。
    """
    sum_cells = sorted(sum_row.cells.items())
    if not sum_cells:
        return None
    sum_sig = "".join(ch for _, ch in sum_cells)
    sum_cols = [dgrid(c) for c, _ in sum_cells]
    digit_only = "".join(ch for ch in product_display if ch.isdigit())
    if not sum_sig or len(digit_only) < len(sum_sig) or not digit_only.endswith(sum_sig):
        return None
    lead = len(digit_only) - len(sum_sig)
    col_l = min(sum_cols) - lead
    if col_l < 0:
        return None
    nd = sum(1 for c in product_display if c.isdigit())
    col_r = col_l + (nd - 1)
    return col_l, col_r


def _strip_verify_product_cols_frac_zeros_after_sum(
    sum_row: DigitRow,
    product_display: str,
    dgrid,
) -> tuple[int, int] | None:
    """
    内层和行是整数积（如 100），教材上又在真积补「.0…」并划末尾 0 时：
    整数部分各位与和行同列，小数点及小数段仅占和行最右列右侧连续列（如 250×0.4 → 100.0）。
    避免 digit_only「1000」与和行「100」位数不等时误用 col_range_fb 把整块积右移。
    """
    if "." not in product_display:
        return None
    ip, fp = product_display.split(".", 1)
    if not fp or any(ch != "0" for ch in fp):
        return None
    dig_ip = "".join(ch for ch in ip if ch.isdigit())
    sum_cells = sorted(sum_row.cells.items())
    if not sum_cells:
        return None
    sum_sig = "".join(ch for _, ch in sum_cells)
    if dig_ip != sum_sig:
        return None
    sum_cols = [dgrid(c) for c, _ in sum_cells]
    col_l = min(sum_cols)
    nd = sum(1 for c in product_display if c.isdigit())
    col_r = col_l + (nd - 1)
    if col_l < 0:
        return None
    return col_l, col_r


def _verify_product_col_range(
    product_display: str, W: int, decimal_shift: int
) -> tuple[int, int] | None:
    """真积按列对齐：与整数积同列网格，右移 (小数位数 − decimal_shift) 列以容纳补位尾 0。列越界则返回 None。"""
    if "." in product_display:
        ip, fp = product_display.split(".", 1)
    else:
        ip, fp = product_display, ""
    nd = len(ip) + len(fp)
    if nd == 0:
        return None
    col_r = (W - 1) + max(0, len(fp) - decimal_shift)
    col_l = col_r - (nd - 1)
    if col_l < 0:
        return None
    return col_l, col_r


def _mul_product_char_center_on_grid(
    j: int,
    product_display: str,
    col_l: int,
    col_x: list[float],
    cw: float,
    st: Style | None = None,
) -> float | None:
    ch = product_display[j]
    if ch == ".":
        dot_i = product_display.index(".")
        ip_len = dot_i
        if ip_len <= 0:
            if 0 <= col_l < len(col_x):
                return col_x[col_l] - cw * 0.42
            return None
        c_l = col_l + ip_len - 1
        if st is not None and 0 <= c_l < len(col_x):
            return _mul_dot_x_hug_left_digit(c_l, col_x, st)
        c_r = col_l + ip_len
        if 0 <= c_l < len(col_x) and 0 <= c_r < len(col_x):
            return (col_x[c_l] + col_x[c_r]) * 0.5
        return None
    if not ch.isdigit():
        return None
    nd_before = sum(1 for ii in range(j) if product_display[ii].isdigit())
    c = col_l + nd_before
    if 0 <= c < len(col_x):
        return col_x[c]
    return None


def _mul_frac_shift_pad_zero_count(fp: str) -> int:
    """小数点后、因数位左移而写在首个非 0 前的 0 的个数（用于红字）。

    - 如 0.048 的「0」在 48 之前 → 1。
    - 如 100.0 仅一位小数且为 0 → 1。
    - 如 256.00 两段尾 0 均不视为左移补位 → 0（仍用黑字 + 斜线）。
    """
    t = fp.rstrip("0")
    if not t:
        return 1 if len(fp) == 1 else 0
    for i, ch in enumerate(fp):
        if ch.isdigit() and ch != "0":
            return i
    return 0


def _school_mul_layout_max_digit_col(layout: SchoolMultiplyLayout) -> int:
    m = 0
    for c in layout.top.cells:
        m = max(m, c)
    for c in layout.bot.cells:
        m = max(m, c)
    for carries, prow in layout.partial_rows:
        for cd in carries:
            m = max(m, cd.col)
        for c in prow.cells:
            m = max(m, c)
    for c in layout.sum_row.cells:
        m = max(m, c)
    for cd in layout.sum_carry:
        m = max(m, cd.col)
    return m


def _mul_verify_product_align_meta(
    int_layout: SchoolMultiplyLayout,
    product_display: str,
) -> tuple[int, int]:
    """验算乘法（无 strip 尾零）：内层列整体右移量，及真积横式中「与内层和行对齐前的补位 0」个数（用于红字）。"""
    sum_cells = sorted(int_layout.sum_row.cells.items())
    if not sum_cells:
        return 0, 0
    sum_sig = "".join(ch for _, ch in sum_cells)
    digit_only = "".join(ch for ch in product_display if ch.isdigit())
    if not sum_sig or len(digit_only) < len(sum_sig) or not digit_only.endswith(sum_sig):
        return 0, 0
    lead = len(digit_only) - len(sum_sig)
    col_l_align = min(c for c, _ in sum_cells) - lead
    inner_shift = max(0, -col_l_align)
    return inner_shift, lead


def _mul_product_str_digit_index_to_col(product_display: str, col_l: int) -> dict[int, int]:
    """
    横式积在列网格上从左到右逐数字占列 → 与 product_display 中各数字字元的下标对应（不含小数点）。
    与 _mul_draw_product_on_digit_grid 的 c = col_l + k 规则一致，供真积行小数点与因子行同规则（紧挨左数）。
    """
    out: dict[int, int] = {}
    k = 0
    for j, ch in enumerate(product_display):
        if ch == ".":
            continue
        if ch.isdigit():
            out[j] = col_l + k
            k += 1
    return out


def _mul_draw_product_on_digit_grid(
    product_display: str,
    col_l: int,
    prod_y: float,
    col_x: list[float],
    cw: float,
    parts: list[str],
    ff: str,
    pfs: float,
    fill: str,
    *,
    decimal_fill: str | None = None,
    lead_pad_digit_count: int = 0,
    st: Style | None = None,
) -> None:
    if "." in product_display:
        ip, fp = product_display.split(".", 1)
    else:
        ip, fp = product_display, ""
    k = 0
    di_global = 0
    for ch in ip:
        if not ch.isdigit():
            continue
        c = col_l + k
        k += 1
        if 0 <= c < len(col_x):
            is_lead0 = (
                decimal_fill is not None
                and lead_pad_digit_count > 0
                and di_global < lead_pad_digit_count
                and ch == "0"
            )
            fill_ch = decimal_fill if is_lead0 else fill
            parts.append(_text(col_x[c], prod_y, ch, fs=pfs, fill=fill_ch, font_family=ff))
        di_global += 1
    if "." in product_display:
        j_dot = product_display.index(".")
        ip_len = len(ip)
        xd: float
        if st is not None and ip_len > 0:
            c_ld = col_l + ip_len - 1
            if 0 <= c_ld < len(col_x):
                xd = _mul_dot_x_hug_left_digit(c_ld, col_x, st)
            else:
                xd = col_x[0]
        elif ip_len > 0:
            c_l = col_l + ip_len - 1
            c_r = col_l + ip_len
            if 0 <= c_l < len(col_x) and 0 <= c_r < len(col_x):
                xd = (col_x[c_l] + col_x[c_r]) * 0.5
            elif 0 <= col_l + ip_len - 1 < len(col_x):
                xd = col_x[col_l + ip_len - 1] + cw * 0.12
            else:
                xd = col_x[0]
        else:
            xd = col_x[col_l] - cw * 0.42 if 0 <= col_l < len(col_x) else col_x[0]
        dot_fill = decimal_fill if decimal_fill is not None else fill
        parts.append(_text(xd, prod_y, ".", fs=pfs, fill=dot_fill, font_family=ff))
    fz_pad = _mul_frac_shift_pad_zero_count(fp)
    fp_di = 0
    for ch in fp:
        if not ch.isdigit():
            continue
        c = col_l + k
        k += 1
        if 0 <= c < len(col_x):
            is_lead0 = (
                decimal_fill is not None
                and lead_pad_digit_count > 0
                and di_global < lead_pad_digit_count
                and ch == "0"
            )
            is_pad0 = fz_pad > 0 and fp_di < fz_pad and ch == "0"
            fill_ch = (
                decimal_fill if (decimal_fill is not None and (is_pad0 or is_lead0)) else fill
            )
            parts.append(_text(col_x[c], prod_y, ch, fs=pfs, fill=fill_ch, font_family=ff))
        fp_di += 1
        di_global += 1


def _mul_inner_bot_right_anchor_col(int_layout: SchoolMultiplyLayout, dgrid) -> int | None:
    """内层乘数最右数字所在列（横式 30→3、800→8）；积行末位有效数字与该列对齐。"""
    if not int_layout.bot.cells:
        return None
    return int(dgrid(max(int_layout.bot.cells.keys())))


def _mul_trailing_fractional_zero_run_indices(product_display: str, dot_j: int) -> list[int]:
    """小数点后、自右向左连续为「0」的字符下标，升序（左→右）。"""
    out: list[int] = []
    jj = len(product_display) - 1
    while jj > dot_j:
        if product_display[jj] == "0":
            out.append(jj)
            jj -= 1
        else:
            break
    out.reverse()
    return out


def _mul_split_core_and_echo_trailing_frac_zeros(
    product_display: str, dot_j: int
) -> tuple[str, list[int]]:
    """横式积拆成（对齐用核心串, 右侧补零待划的下标列表）；补零不参与从右反推的数位对齐。"""
    idxs = _mul_trailing_fractional_zero_run_indices(product_display, dot_j)
    if not idxs:
        return product_display, []
    return product_display[: idxs[0]], idxs


def _mul_strip_core_frac_pad_red_flags(core: str) -> dict[int, bool]:
    """core 横式串中，小数点后因数位左移而写的连续 0（与 _mul_frac_shift_pad_zero_count 一致）→ 红字。"""
    out: dict[int, bool] = {}
    if "." not in core:
        return out
    dj = core.index(".")
    fp_c = core[dj + 1 :]
    fz = _mul_frac_shift_pad_zero_count(fp_c)
    if fz <= 0:
        return out
    fp_idx = 0
    for j in range(dj + 1, len(core)):
        ch = core[j]
        if not ch.isdigit():
            continue
        if ch == "0" and fp_idx < fz:
            out[j] = True
        fp_idx += 1
    return out


def _mul_draw_product_strip_anchor_left(
    product_display: str,
    *,
    anchor_col: int,
    prod_y: float,
    col_x: list[float],
    cw: float,
    parts: list[str],
    ff: str,
    pfs: float,
    fill: str,
    decimal_fill: str,
    st: Style,
    fs: float,
    c_red: str,
) -> None:
    """strip 单行积：末位有效数字与内层乘数最右列对齐，向左依次占列；小数点紧挨左侧数字；补零仍在末位数字右侧。"""
    if "." not in product_display:
        return
    dot_full = product_display.index(".")
    core, echo_idx = _mul_split_core_and_echo_trailing_frac_zeros(product_display, dot_full)
    pad_red = _mul_strip_core_frac_pad_red_flags(core)
    slots: list[tuple[int, str]] = []
    for j in range(len(core) - 1, -1, -1):
        if core[j].isdigit():
            slots.append((j, core[j]))
    if not slots:
        return
    digit_col: dict[int, int] = {}
    for k, (j, ch) in enumerate(slots):
        c = anchor_col - k
        digit_col[j] = c
        if 0 <= c < len(col_x):
            fill_ch = c_red if pad_red.get(j) else fill
            parts.append(_text(col_x[c], prod_y, ch, fs=pfs, fill=fill_ch, font_family=ff))
    last_digit_col = digit_col[slots[0][0]]
    if "." in core:
        dj = core.index(".")
        li, ri = dj - 1, dj + 1
        if (
            li >= 0
            and ri < len(core)
            and core[li].isdigit()
            and core[ri].isdigit()
            and li in digit_col
            and ri in digit_col
        ):
            c_l = digit_col[li]
            if 0 <= c_l < len(col_x):
                xd = _mul_dot_x_hug_left_digit(c_l, col_x, st)
                parts.append(_text(xd, prod_y, ".", fs=pfs, fill=decimal_fill, font_family=ff))
        elif core.endswith(".") and echo_idx:
            # 核心串以「.」结尾、小数位在 echo 列（如 100. + 0 → 100.0）：在两列中缝画小数点，避免画成 1000
            li = dj - 1
            if li >= 0 and li in digit_col:
                c_ld = digit_col[li]
                c_first0 = last_digit_col + 1
                if 0 <= c_ld < len(col_x) and 0 <= c_first0 < len(col_x):
                    xd = _mul_dot_x_hug_left_digit(c_ld, col_x, st)
                    parts.append(_text(xd, prod_y, ".", fs=pfs, fill=decimal_fill, font_family=ff))
    if echo_idx:
        hw = _strike_zero_half_width(st)
        for t, ei in enumerate(echo_idx):
            c = last_digit_col + 1 + t
            if not (0 <= c < len(col_x)):
                continue
            ch = product_display[ei]
            # echo 为量化/对齐补在横式上的尾 0，与红小数点同为「补位」书写
            parts.append(_text(col_x[c], prod_y, ch, fs=pfs, fill=c_red, font_family=ff))
            parts.append(_strike_uniform(col_x[c], _strike_y_for_zero(prod_y, fs), hw, c_red))
        frac = product_display[dot_full + 1 :]
        if frac and all(c == "0" for c in frac):
            c_ld = last_digit_col
            c_first0 = last_digit_col + 1
            if 0 <= c_ld < len(col_x) and 0 <= c_first0 < len(col_x):
                xd = _mul_dot_x_hug_left_digit(c_ld, col_x, st)
                cy_s = _strike_y_for_glyph(".", prod_y, fs)
                hw_dot = _strike_half_width_dot(fs, _char_width(".", st))
                parts.append(_strike_uniform(xd, cy_s, hw_dot, c_red))


def _digit_row_sig(row: DigitRow) -> str:
    return "".join(ch for _, ch in sorted(row.cells.items()))


def _remap_digit_row_cells(row: DigitRow, pad: int) -> DigitRow:
    return DigitRow({c + pad: ch for c, ch in row.cells.items()})


def _remap_carries(carries: list, pad: int) -> list[CarryDigit]:
    out: list[CarryDigit] = []
    for c in carries:
        nc = c.col + pad
        if nc >= 0:
            out.append(CarryDigit(col=nc, ch=c.ch, dy=c.dy))
    return out


def _mul_strike_trailing_fractional_zeros_grid(
    product_display: str,
    col_l: int,
    prod_y: float,
    col_x: list[float],
    cw: float,
    st: Style,
    parts: list[str],
    fs: float,
    c_red: str,
) -> None:
    if "." not in product_display:
        return
    dot_i = product_display.index(".")
    strike_j: list[int] = []
    for jj in range(len(product_display) - 1, dot_i, -1):
        if product_display[jj] == "0":
            strike_j.append(jj)
        else:
            break
    if not strike_j:
        return
    hw = _strike_zero_half_width(st)
    for jj in strike_j:
        cx = _mul_product_char_center_on_grid(
            jj, product_display, col_l, col_x, cw, st=st
        )
        if cx is None:
            continue
        parts.append(_strike_uniform(cx, _strike_y_for_zero(prod_y, fs), hw, c_red))
    if _mul_should_strike_dot_after_frac_trailing_zeros(product_display, dot_i, strike_j):
        cx_dot = _mul_product_char_center_on_grid(
            dot_i, product_display, col_l, col_x, cw, st=st
        )
        if cx_dot is not None:
            cy_s = _strike_y_for_glyph(".", prod_y, fs)
            hw_dot = _strike_half_width_dot(fs, _char_width(".", st))
            parts.append(_strike_uniform(cx_dot, cy_s, hw_dot, c_red))


# 验算乘法「×」：无整数网格的简化三行布局时，相对乘数行左缘左移（格宽倍数）
_MUL_VERIFY_TIMES_OFFSET_CW = 1.72
_MUL_VERIFY_TIMES_MIN_X_MARGIN = 0.18
# 乘数行下到「第一条部分积横线」的间距系数（越小横线越靠上；进位不展示时可更小）
_MUL_VERIFY_RULE1_AFTER_TIMES_ROW = 0.76
_MUL_VERIFY_RULE1_AFTER_TIMES_ROW_NO_CARRY = 0.50
# 第一行部分积进位：红字垂直中心在横线上方固定距离（px；SVG y 向下为正）
_MUL_FIRST_ROW_CARRY_ABOVE_RULE_PX = 4.0
# 竖式「× / + / −」与横线：相对最左参与数字列、乘号字身左缘的几何规则（与加减法一致）
_SYM_RULE_GAP_PX = 4.0


def _glyph_half_width_times_or_plus(fs: float, cw: float) -> float:
    return max(fs * 0.22, cw * 0.18)


def _verify_times_center_and_rule_x1(
    col_x: list[float], cw: float, margin: float, min_digit_col: int, fs: float
) -> tuple[float, float]:
    """
    乘号「×」：最左参与数字列左缘再往左 4px 为乘号字身右缘；横线 x1 为乘号字身左缘再往左 4px。
    返回 (× 的 text-anchor=middle 中心 x, 第一条横线左端 x1)。
    """
    if not col_x:
        return margin * _MUL_VERIFY_TIMES_MIN_X_MARGIN + cw * 0.25, 2.0
    dc = max(0, min(int(min_digit_col), len(col_x) - 1))
    digit_left = col_x[dc] - cw * 0.5
    sym_hw = _glyph_half_width_times_or_plus(fs, cw)
    sym_right = digit_left - _SYM_RULE_GAP_PX
    x_times = sym_right - sym_hw
    sym_left = x_times - sym_hw
    rule_x1 = max(2.0, sym_left - _SYM_RULE_GAP_PX)
    return x_times, rule_x1


def _int_layout_min_digit_col(layout: SchoolMultiplyLayout) -> int:
    cols = [c for c, ch in layout.top.cells.items() if ch.isdigit()] + [
        c for c, ch in layout.bot.cells.items() if ch.isdigit()
    ]
    return min(cols) if cols else 0


def _add_sub_symbol_x_and_rule_x0(
    col_x: list[float],
    cw: float,
    min_digit_col: int,
    fs: float,
) -> tuple[float, float]:
    """加/减号：与验算 × 相同（最左数字列左缘左 4px 为符号右缘）；横线起点为符号字身左缘再左 4px。"""
    dc = max(0, min(int(min_digit_col), len(col_x) - 1))
    digit_left = col_x[dc] - cw * 0.5
    sym_hw = _glyph_half_width_times_or_plus(fs, cw)
    sym_right = digit_left - _SYM_RULE_GAP_PX
    x_sym = sym_right - sym_hw
    sym_left = x_sym - sym_hw
    rule_x0 = max(2.0, sym_left - _SYM_RULE_GAP_PX)
    return x_sym, rule_x0


def _digits_only_in_order(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _factor_display_matches_inner_row(display: str, row: DigitRow) -> bool:
    sig = _digit_row_sig(row)
    d = _digits_only_in_order(display)
    return len(d) == len(sig) and d == sig


def _draw_factor_decimal_on_int_grid(
    display: str,
    row: DigitRow,
    col_x: list[float],
    y: float,
    st: Style,
    parts: list[str],
    ff: str,
    fs: float,
    fill: str,
) -> bool:
    """
    将带小数点的横式因子画在整数竖式列上：数字与 inner DigitRow 逐位对齐，小数点紧挨左侧数字（与乘法竖式通例一致）。
    仅当「去掉非数字后的数字串」与 inner 行一致时返回 True。
    """
    if not _factor_display_matches_inner_row(display, row):
        return False
    sig = _digit_row_sig(row)
    cols = [c for c, _ in sorted(row.cells.items())]
    digit_idx_in_display = [i for i, ch in enumerate(display) if ch.isdigit()]
    if len(digit_idx_in_display) != len(cols):
        return False
    for k, i in enumerate(digit_idx_in_display):
        if display[i] != sig[k]:
            return False
    pos_col: dict[int, int] = {}
    for k, i in enumerate(digit_idx_in_display):
        cc = cols[k]
        if not (0 <= cc < len(col_x)):
            return False
        pos_col[i] = cc
    for j, ch in enumerate(display):
        if ch.isdigit():
            parts.append(_text(col_x[pos_col[j]], y, ch, fs=fs, fill=fill, font_family=ff))
        elif ch == ".":
            left = j - 1
            right = j + 1
            wd0 = _char_width("0", st)
            if left in pos_col and right in pos_col:
                c_l = pos_col[left]
                if 0 <= c_l < len(col_x):
                    xd = _mul_dot_x_hug_left_digit(c_l, col_x, st)
                else:
                    return False
            elif right in pos_col:
                c0 = pos_col[right]
                xd = col_x[c0] - 0.5 * wd0 if c0 >= 0 else col_x[0]
            elif left in pos_col:
                c0 = pos_col[left]
                xd = _mul_dot_x_hug_left_digit(c0, col_x, st) if 0 <= c0 < len(col_x) else col_x[-1]
            else:
                return False
            parts.append(_text(xd, y, ".", fs=fs, fill=fill, font_family=ff))
        elif ch.isspace():
            continue
        else:
            return False
    return True


def _strip_verify_row_pos_col(
    display: str,
    row: DigitRow,
    dcol_fn: object,
    grid_shift: int,
) -> dict[int, int] | None:
    """横式因子（可含小数点）相对内层 DigitRow 的字符下标 → 画布列号；无法 strip 对齐时返回 None。"""
    sig = _digit_row_sig(row)
    d_all = _digits_only_in_order(display)
    if len(d_all) < len(sig):
        return None
    ib_pairs = sorted(row.cells.items())
    if len(ib_pairs) != len(sig):
        return None
    for k, (_, ich) in enumerate(ib_pairs):
        if ich != sig[k]:
            return None
    digit_indices = [i for i, ch in enumerate(display) if ch.isdigit()]
    if len(digit_indices) != len(d_all):
        return None

    pos_col: dict[int, int] = {}
    mode: str | None = None
    extra_lead = 0
    extra_trail = 0
    if d_all.endswith(sig):
        extra_lead = len(d_all) - len(sig)
        if extra_lead == 0 or all(ch == "0" for ch in d_all[:extra_lead]):
            mode = "lead"
    if mode is None and d_all.startswith(sig):
        extra_trail = len(d_all) - len(sig)
        if extra_trail == 0 or all(ch == "0" for ch in d_all[len(sig) :]):
            mode = "trail"
    if mode is None:
        return None

    if mode == "lead":
        first_ic = ib_pairs[0][0]
        fc0 = dcol_fn(first_ic) + grid_shift
        for t in range(extra_lead):
            pos_col[digit_indices[t]] = fc0 - (extra_lead - t)
        for k in range(len(sig)):
            pos_col[digit_indices[extra_lead + k]] = dcol_fn(ib_pairs[k][0]) + grid_shift
    else:
        for k in range(len(sig)):
            pos_col[digit_indices[k]] = dcol_fn(ib_pairs[k][0]) + grid_shift
        last_ic = ib_pairs[-1][0]
        right0 = dcol_fn(last_ic) + grid_shift
        for t in range(extra_trail):
            pos_col[digit_indices[len(sig) + t]] = right0 + 1 + t
    return pos_col


def _append_strip_verify_factor_row_parts(
    display: str,
    pos_col: dict[int, int],
    col_x: list[float],
    y: float,
    st: Style,
    parts: list[str],
    ff: str,
    fs: float,
    fill: str,
) -> bool:
    for j, ch in enumerate(display):
        if ch.isdigit():
            c = pos_col.get(j)
            if c is None or not (0 <= c < len(col_x)):
                return False
            parts.append(_text(col_x[c], y, ch, fs=fs, fill=fill, font_family=ff))
        elif ch == ".":
            left = j - 1
            right = j + 1
            wd0 = _char_width("0", st)
            if left in pos_col and right in pos_col:
                c_l = pos_col[left]
                if 0 <= c_l < len(col_x):
                    xd = _mul_dot_x_hug_left_digit(c_l, col_x, st)
                else:
                    return False
            elif right in pos_col:
                c0 = pos_col[right]
                xd = col_x[c0] - 0.5 * wd0 if c0 >= 0 else col_x[0]
            elif left in pos_col:
                c0 = pos_col[left]
                xd = _mul_dot_x_hug_left_digit(c0, col_x, st) if 0 <= c0 < len(col_x) else col_x[-1]
            else:
                return False
            parts.append(_text(xd, y, ".", fs=fs, fill=fill, font_family=ff))
        elif ch.isspace():
            continue
        else:
            return False
    return True


def _draw_strip_verify_bot_row(
    display: str,
    bot_row: DigitRow,
    col_x: list[float],
    y: float,
    dcol_fn: object,
    st: Style,
    parts: list[str],
    ff: str,
    fs: float,
    fill: str,
    *,
    grid_shift: int = 0,
) -> bool:
    """
    验算乘数行：横式可与内层整数乘数逐位对齐。
    - 多「仅前导 0」：如 0.016 对 inner 16，前导 0 排在首内层数字列左侧（与原先一致）。
    - 多「仅末尾 0」（整十整百书写）：如 30/800 对 inner 3/8，有效数字与内层同列，末尾 0 依次排在
      内层乘数最右数字列右侧，不参与竖式进位列对齐（仅占位）。
    """
    pos_col = _strip_verify_row_pos_col(display, bot_row, dcol_fn, grid_shift)
    if pos_col is None:
        return False
    return _append_strip_verify_factor_row_parts(
        display, pos_col, col_x, y, st, parts, ff, fs, fill
    )


def _verify_mul_column_centers_uniform(W_eff: int, st: Style, margin: float) -> dict[int, float]:
    """验算块横式因子的数位列心：与内层列号一一对应的等距格（`cell_w` 一格一字）。

    不再用横式逐字心 + 下行链式回写同列，否则上因子末位补零等「不参与竖式进位但横式照写」
    时会与下因子同列心抢格、出现不等距（如 250×0.4 上行 2—5 与 5—0 间距不一）。
    """
    cw = st.cell_w
    return {c: margin + (c + 0.5) * cw for c in range(W_eff)}


def _verify_mul_known_strips(
    W_eff: int,
    st: Style,
    margin: float,
    grid0: int,
    dgrid,
    factor_top: str,
    factor_bot: str,
    pos_top_strip: dict[int, int] | None,
    pos_bot_strip: dict[int, int] | None,
    *,
    prefix_len: int,
    mul_core_len: int,
    ml: int,
    mx_top: int,
) -> dict[int, float]:
    return _verify_mul_column_centers_uniform(W_eff, st, margin)


def _verify_mul_known_from_pos(
    W_eff: int,
    st: Style,
    margin: float,
    factor_top: str,
    factor_bot: str,
    top_pos: dict[int, int] | None,
    bot_pos: dict[int, int] | None,
) -> dict[int, float]:
    if top_pos is None or bot_pos is None:
        return {}
    return _verify_mul_column_centers_uniform(W_eff, st, margin)


def render_verification_multiplication_svg(
    *,
    factor_top_display: str,
    factor_bot_display: str,
    product_display: str,
    int_layout: SchoolMultiplyLayout | None,
    product_decimal_shift: int | None = None,
    verification_strip_trailing_int: int = 0,
    st: Style | None = None,
) -> tuple[str, float, float, int | None, float]:
    """验算乘法竖式（不含「验算：」标签）；部分积/求和进位颜色受 `render_config` 控制。

    返回 (svg, width, height, digit_grid_columns, ink_right)：
    - digit_grid_columns：列式数字网格宽度（与 margin 两侧留白无关），无整数列网格时为 None；用于与下方加法验算等对齐列宽。
    - ink_right：竖式主墨迹（长横线、或纯文本三行时末行数字）最右侧 x 坐标，不含 SVG 右缘白边。

    verification_strip_trailing_int：横式商右侧可与列竖式剥离的尾零个数（由 compose 在数值一致前提下传入）。
    大于 0 时仅用于横式因子与真积书写（含划去小数尾 0）；**不在**部分积行末再补甩下的 0（中间过程与内层整数乘一致）。
    若内层整数乘**仅一行部分积**且**无求和进位**（单数位乘数等），
    则省略该部分积数字行与第二条横线，在首条横线后直接写真积（点小数、划末尾 0），如 0.5×2 不再单独画「10」过渡行。
    """
    st = st or Style()
    fs = st.font_size
    c_main = st.color_main
    c_red = _remark_color(st)
    ff = st.font_family
    margin = 16.0
    cw = st.cell_w
    row_h = fs * 1.08
    parts: list[str] = []
    verify_digit_grid_cols: int | None = None

    gap_below_rule = fs * 0.58
    row_gap_partial = row_h * 0.95
    rule1_after = (
        _MUL_VERIFY_RULE1_AFTER_TIMES_ROW
        if render_config.SHOW_CARRY_BORROW_DIGITS
        else _MUL_VERIFY_RULE1_AFTER_TIMES_ROW_NO_CARRY
    )

    if int_layout is not None and verification_strip_trailing_int > 0:
        # 验算列与「去商尾零后的整数因子 × 移位整数」对齐；横式仍画完整商与除数；甩下的商尾零画在部分积行右侧。
        multicore = _digit_row_sig(int_layout.top)
        mulc_str = _digit_row_sig(int_layout.bot)
        prefix_len = factor_top_display.find(multicore)
        if prefix_len < 0:
            prefix_len = 0
        ml = min(int_layout.top.cells)
        pad = prefix_len - ml
        idx_bot = factor_bot_display.find(mulc_str)
        if idx_bot < 0:
            idx_bot = 0
        lsd_mc = max(int_layout.top.cells)

        def dcol(c: int) -> int:
            return c + pad

        # 内层列用 dcol 后若出现负列，整体右移 grid0，使部分积个位仍与乘数同列、上行下沿数位竖直对齐
        grid0 = 0
        for _c, prow in int_layout.partial_rows:
            for c in prow.cells:
                grid0 = max(grid0, -(c + pad))
        for c in int_layout.sum_row.cells:
            grid0 = max(grid0, -(c + pad))
        for c in int_layout.bot.cells:
            grid0 = max(grid0, -(c + pad))
        for c in int_layout.top.cells:
            grid0 = max(grid0, -(c + pad))

        # 乘数横式可能比内层多「仅前导 0」的数位（如 0.016 对 inner 16）：左侧列须 >=0，
        # 否则 _draw_strip_verify_bot_row 失败走回退路径会丢弃 cj<0 的字符（只剩 ×016），且 W/col_range 偏小导致真积错位。
        bot_sig = _digit_row_sig(int_layout.bot)
        dbot_digits = _digits_only_in_order(factor_bot_display)
        bot_lead_extra = 0
        if (
            len(dbot_digits) >= len(bot_sig)
            and dbot_digits.endswith(bot_sig)
            and (len(dbot_digits) == len(bot_sig) or all(ch == "0" for ch in dbot_digits[: len(dbot_digits) - len(bot_sig)]))
        ):
            bot_lead_extra = len(dbot_digits) - len(bot_sig)
        if bot_lead_extra:
            fb0 = min(int_layout.bot.cells) + pad
            grid0 = max(grid0, bot_lead_extra - fb0)

        if "." not in factor_top_display:
            top_sig = _digit_row_sig(int_layout.top)
            dtop_digits = _digits_only_in_order(factor_top_display)
            top_lead_extra = 0
            if (
                len(dtop_digits) >= len(top_sig)
                and dtop_digits.endswith(top_sig)
                and (
                    len(dtop_digits) == len(top_sig)
                    or all(ch == "0" for ch in dtop_digits[: len(dtop_digits) - len(top_sig)])
                )
            ):
                top_lead_extra = len(dtop_digits) - len(top_sig)
            if top_lead_extra:
                ft0 = min(int_layout.top.cells) + pad
                grid0 = max(grid0, top_lead_extra - ft0)

        def dgrid(c: int) -> int:
            return c + pad + grid0

        maxc = max(len(factor_top_display) - 1 + grid0, len(factor_bot_display) - 1 + grid0)
        for _carries, prow in int_layout.partial_rows:
            for c in prow.cells:
                maxc = max(maxc, dgrid(c))
        last_prow = int_layout.partial_rows[-1][1]
        mxp = max(last_prow.cells) if last_prow.cells else 0
        # 真积列宽：仅以内层积/和行右缘为准；乘数横式末尾整十整百的 0 已用 _draw_strip_verify_bot_row 画在
        # 内层乘数最右列右侧，不再并入 W 去推积，避免 0.032×800 与 trail==1 特判互相打架。
        maxc_inner_right = max(
            maxc,
            dgrid(mxp),
            max((dgrid(c) for c in int_layout.sum_row.cells), default=0),
        )
        # 商尾零（verification_strip_trailing_int）只体现在横式因子与**最终积**上，不在部分积行右侧再画 0：
        # 中间过程与内层整数乘一致（如第二行部分积为 16 而非 1600）；甩下列宽不再并入 maxc。
        maxc = maxc_inner_right

        # 与部分积 + 和行最右列一致，不能用 width+trail（会短于实际列如 25600）
        Wp = maxc + 1
        W_mul_for_product_range = maxc_inner_right + 1
        col_range_fb = (
            _verify_product_col_range(
                product_display, W_mul_for_product_range, product_decimal_shift
            )
            if product_decimal_shift is not None
            else None
        )
        sum_align = None
        int_frac_sum_align = None
        if int_layout.sum_row.cells:
            sum_align = _strip_verify_product_cols_from_sum(
                int_layout.sum_row, product_display, dgrid
            )
            int_frac_sum_align = _strip_verify_product_cols_frac_zeros_after_sum(
                int_layout.sum_row, product_display, dgrid
            )
        # 与和行逐数字同列（sum_align）在「积的数字位数 = 和行位数」时会把真积左移一列（如 12.6/126），
        # 与 compose 传入的 product_decimal_shift 所对应的 _verify_product_col_range 不一致，导致 6 与上行 2 同列。
        # 当横式积去掉非数字后末段与和行一致且位数相同（无额前导数字位）时，以 col_range_fb 为准；否则仍用 sum_align（如 0.48 对 48）。
        digit_only_fb = "".join(ch for ch in product_display if ch.isdigit())
        sum_sig_fb = (
            "".join(ch for _, ch in sorted(int_layout.sum_row.cells.items()))
            if int_layout.sum_row.cells
            else ""
        )
        prefer_product_shift_cols = (
            col_range_fb is not None
            and sum_sig_fb
            and digit_only_fb.endswith(sum_sig_fb)
            and len(digit_only_fb) == len(sum_sig_fb)
        )
        if int_frac_sum_align is not None:
            _col_l, col_r = int_frac_sum_align
            W_eff = max(maxc + 1, col_r + 1)
        elif prefer_product_shift_cols:
            _col_l, col_r = col_range_fb
            W_eff = max(maxc + 1, col_r + 1)
        elif sum_align is not None:
            _col_l, col_r = sum_align
            W_eff = max(maxc + 1, col_r + 1)
        elif col_range_fb is not None:
            _col_l, col_r = col_range_fb
            W_eff = max(maxc + 1, col_r + 1)
        else:
            _col_l = -1
            W_eff = max(maxc + 1, Wp)
        # strip 单行积：echo 尾零在 anchor 右侧连续列；W 仅按内层右缘会少列，末位补 0 画不出（如 0.480→0.48）
        if (
            _col_l >= 0
            and "." in product_display
            and int_layout is not None
            and len(int_layout.partial_rows) == 1
            and not int_layout.sum_carry
            and int_layout.sum_row.cells
            and int_layout.bot.cells
        ):
            dj_e = product_display.index(".")
            core_e, echo_list_e = _mul_split_core_and_echo_trailing_frac_zeros(product_display, dj_e)
            if echo_list_e and "." in core_e:
                anchor_e = _mul_inner_bot_right_anchor_col(int_layout, dgrid)
                if anchor_e is not None:
                    need_w = anchor_e + 1 + len(echo_list_e)
                    if need_w > W_eff:
                        W_eff = need_w
        Lm = len(multicore)
        mx_top = max(int_layout.top.cells) if int_layout.top.cells else ml
        pos_top_strip = (
            _strip_verify_row_pos_col(factor_top_display, int_layout.top, dcol, grid0)
            if "." in factor_top_display
            else None
        )
        pos_bot_strip = _strip_verify_row_pos_col(
            factor_bot_display, int_layout.bot, dcol, grid0
        )
        # 末位整十/整百的尾 0 在 pos_bot_strip 中可能为 maxc+1（如 0.016×30 内层 3 已占最右列）
        if pos_top_strip is not None or pos_bot_strip is not None:
            s_max = 0
            for pc in (pos_top_strip, pos_bot_strip):
                if pc:
                    s_max = max(s_max, max(pc.values(), default=0))
            W_eff = max(W_eff, s_max + 1)
        known_s = _verify_mul_known_strips(
            W_eff,
            st,
            margin,
            grid0,
            dgrid,
            factor_top_display,
            factor_bot_display,
            pos_top_strip,
            pos_bot_strip,
            prefix_len=prefix_len,
            mul_core_len=Lm,
            ml=ml,
            mx_top=mx_top,
        )
        if known_s:
            col_x = _col_x_from_known_columns(W_eff, known_s, margin, cw)
        else:
            col_x = [margin + (i + 0.5) * cw for i in range(W_eff)]
        block_right = col_x[-1] + 0.5 * cw if W_eff > 0 else margin
        gap_b = max(fs * 0.72, gap_below_rule)

        y = margin + fs * 0.35
        # 乘号：以上下因子在网格中的最左列为锚（教材 × 在全体因子数字之左），避免下行 0.016 比上行更靠左时压住乘数
        min_top_col = 10**9
        if "." not in factor_top_display:
            for j, ch in enumerate(factor_top_display):
                if ch.isdigit() and prefix_len <= j < prefix_len + Lm:
                    ic = ml + (j - prefix_len)
                    jc = dgrid(ic)
                elif ch.isdigit():
                    jc = dgrid(mx_top) + (j - (prefix_len + Lm - 1))
                else:
                    continue
                min_top_col = min(min_top_col, jc)
        elif pos_top_strip is not None:
            min_top_col = min(pos_top_strip.values())
        else:
            for j, ch in enumerate(factor_top_display):
                if ch.isdigit():
                    min_top_col = min(min_top_col, j + grid0)
        first_ic_bot = min(int_layout.bot.cells)
        fc0_bot = dcol(first_ic_bot) + grid0
        min_bot_col = (
            (fc0_bot - bot_lead_extra)
            if bot_lead_extra
            else min(dgrid(c) for c in int_layout.bot.cells)
        )
        if min_top_col < 10**8:
            times_anchor_col = max(0, min(min_top_col, min_bot_col))
        else:
            times_anchor_col = dgrid(ml)
        if "." not in factor_top_display:
            for j, ch in enumerate(factor_top_display):
                if ch.isdigit() and prefix_len <= j < prefix_len + Lm:
                    ic = ml + (j - prefix_len)
                    jc = dgrid(ic)
                elif ch.isdigit():
                    jc = dgrid(mx_top) + (j - (prefix_len + Lm - 1))
                else:
                    continue
                if 0 <= jc < len(col_x):
                    parts.append(_text(col_x[jc], y, ch, fs=fs, fill=c_main, font_family=ff))
        elif pos_top_strip is not None:
            if not _append_strip_verify_factor_row_parts(
                factor_top_display,
                pos_top_strip,
                col_x,
                y,
                st,
                parts,
                ff,
                fs,
                c_main,
            ):
                for j, ch in enumerate(factor_top_display):
                    jc = j + grid0
                    if ch == ".":
                        jl = (j - 1) + grid0
                        jr = (j + 1) + grid0
                        if 0 <= jl < len(col_x) and 0 <= jr < len(col_x):
                            xd = (col_x[jl] + col_x[jr]) * 0.5
                            parts.append(_text(xd, y, ".", fs=fs, fill=c_main, font_family=ff))
                    elif ch.isdigit() and 0 <= jc < len(col_x):
                        parts.append(_text(col_x[jc], y, ch, fs=fs, fill=c_main, font_family=ff))
        else:
            for j, ch in enumerate(factor_top_display):
                jc = j + grid0
                if ch == ".":
                    jl = (j - 1) + grid0
                    jr = (j + 1) + grid0
                    if 0 <= jl < len(col_x) and 0 <= jr < len(col_x):
                        xd = (col_x[jl] + col_x[jr]) * 0.5
                        parts.append(_text(xd, y, ".", fs=fs, fill=c_main, font_family=ff))
                elif ch.isdigit() and 0 <= jc < len(col_x):
                    parts.append(_text(col_x[jc], y, ch, fs=fs, fill=c_main, font_family=ff))
        y += row_h
        # 必须用 times_anchor_col（含横式前导 0 的 min_bot_col），勿用 _int_layout_min_digit_col：
        # 否则 × 会按「仅内层」最左列定位，与 0.16 等前导 0 横式重叠（如 256÷0.16 验算 1600×0.16）。
        x_times, rule_x1 = _verify_times_center_and_rule_x1(
            col_x, cw, margin, times_anchor_col, fs
        )
        parts.append(_text(x_times, y, "×", anchor="middle", fs=fs, fill=c_main, font_family=ff))
        if not _draw_strip_verify_bot_row(
            factor_bot_display,
            int_layout.bot,
            col_x,
            y,
            dcol,
            st,
            parts,
            ff,
            fs,
            c_main,
            grid_shift=grid0,
        ):
            base_bot = dgrid(lsd_mc) - idx_bot
            for j, ch in enumerate(factor_bot_display):
                cj = base_bot + j
                if 0 <= cj < len(col_x):
                    parts.append(_text(col_x[cj], y, ch, fs=fs, fill=c_main, font_family=ff))
        y += row_h * rule1_after
        line1_y = y
        parts.append(
            f'<line x1="{rule_x1:.2f}" y1="{line1_y:.2f}" x2="{block_right + margin * 0.35:.2f}" y2="{line1_y:.2f}" '
            f'stroke="{c_main}" stroke-width="1.65" stroke-linecap="round"/>'
        )
        pad_eff = pad + grid0
        # 仅一行部分积且无「多行部分积相加」的求和进位时：部分积数字行与最终积相同（如 5×2→10 与横式 1.0），
        # 省略该行、第二条横线及求和进位，首条横线后直接写真积（点小数、划末尾 0）。含原「商尾零 strip」情形。
        omit_redundant_partial_row = (
            len(int_layout.partial_rows) == 1 and not int_layout.sum_carry
        )
        pfs = fs * 0.95
        use_prod_grid = _col_l >= 0
        if omit_redundant_partial_row:
            # 进位红字仍按第一行部分积的规则画（仅省略过渡数字行，不省略进位信息）
            carries0, _ = int_layout.partial_rows[0]
            rc0 = _remap_carries(carries0, pad_eff)
            y_first_carry = line1_y - _MUL_FIRST_ROW_CARRY_ABOVE_RULE_PX
            _mul_draw_carries(
                rc0, col_x, line1_y, st, parts, ff, fs, cw=cw, y_center_direct=y_first_carry
            )
            gap_prod_below_rule1 = max(fs * 0.72, gap_below_rule * 0.98)
            prod_y = line1_y + gap_prod_below_rule1
            if use_prod_grid:
                col_l_draw = _col_l
                dot_j_full = product_display.index(".") if "." in product_display else -1
                core_for_align, _echo = (
                    _mul_split_core_and_echo_trailing_frac_zeros(product_display, dot_j_full)
                    if dot_j_full >= 0
                    else (product_display, [])
                )
                strip_anchor_prod = (
                    "." in core_for_align
                    and bool(int_layout.sum_row.cells)
                    and bool(int_layout.bot.cells)
                )
                anchor_col = (
                    _mul_inner_bot_right_anchor_col(int_layout, dgrid)
                    if strip_anchor_prod
                    else None
                )
                if strip_anchor_prod and anchor_col is not None:
                    # 末位有效数字与内层乘数最右列对齐，向左依次排；小数点不占与上行对齐的列缝
                    _mul_draw_product_strip_anchor_left(
                        product_display,
                        anchor_col=anchor_col,
                        prod_y=prod_y,
                        col_x=col_x,
                        cw=cw,
                        parts=parts,
                        ff=ff,
                        pfs=pfs,
                        fill=c_main,
                        decimal_fill=c_red,
                        st=st,
                        fs=fs,
                        c_red=c_red,
                    )
                else:
                    # 单行：在列网格上直接画横式积（红小数点、划去小数部分多余 0），与内层和行数位对齐
                    _mul_draw_product_on_digit_grid(
                        product_display,
                        col_l_draw,
                        prod_y,
                        col_x,
                        cw,
                        parts,
                        ff,
                        pfs,
                        c_main,
                        decimal_fill=c_red,
                        st=st,
                    )
                    _mul_strike_trailing_fractional_zeros_grid(
                        product_display, col_l_draw, prod_y, col_x, cw, st, parts, pfs, c_red
                    )
            else:
                grid_right = margin + Wp * cw
                _mul_text_right(product_display, grid_right, prod_y, st, parts, ff, pfs, c_main)
                _mul_strike_trailing_fractional_zeros(product_display, grid_right, prod_y, st, parts, ff, pfs, c_red)
        else:
            y_digit = line1_y + gap_b
            n_part = len(int_layout.partial_rows)
            y_digit_prev = line1_y
            partials_for_rule2: list[tuple[list[CarryDigit], DigitRow]] = []
            for idx, (carries, prow) in enumerate(int_layout.partial_rows):
                rc = _remap_carries(carries, pad_eff)
                rr = _remap_digit_row_cells(prow, pad_eff)
                partials_for_rule2.append((rc, rr))
                if idx == 0:
                    y_first_carry = line1_y - _MUL_FIRST_ROW_CARRY_ABOVE_RULE_PX
                    _mul_draw_carries(
                        rc, col_x, line1_y, st, parts, ff, fs, cw=cw, y_center_direct=y_first_carry
                    )
                else:
                    y_carry = _mul_carry_y_between_partial_rows(y_digit_prev, y_digit, fs)
                    _mul_draw_carries(rc, col_x, y_carry, st, parts, ff, fs, cw=cw)
                _mul_digit_row_cells(rr, col_x, y_digit, st, parts, ff, fs, c_main)
                y_digit_prev = y_digit
                if idx < n_part - 1:
                    y_digit += row_gap_partial
            gap_strip_to_rule2 = max(fs * 0.38, row_h * 0.42)
            line2_y = y_digit + gap_strip_to_rule2
            rule_x2_strip = block_right + margin * 0.35
            prod_rng_strip = (_col_l, col_r) if use_prod_grid and _col_l >= 0 else None
            line2_x1, line2_x2 = _mul_second_rule_line_x1_x2(
                col_x=col_x,
                cw=cw,
                fs=fs,
                rule_x1=rule_x1,
                rule_x2=rule_x2_strip,
                partial_rows=partials_for_rule2,
                product_col_range=prod_rng_strip,
                extra_digit_cols=None,
            )
            parts.append(
                f'<line x1="{line2_x1:.2f}" y1="{line2_y:.2f}" x2="{line2_x2:.2f}" y2="{line2_y:.2f}" '
                f'stroke="{c_main}" stroke-width="1.65" stroke-linecap="round"/>'
            )
            prod_y = line2_y + gap_b
            y_sc = _mul_carry_y_between_rule2_and_product(line2_y, prod_y, fs)
            _mul_draw_carries(
                _remap_carries(int_layout.sum_carry, pad_eff), col_x, y_sc, st, parts, ff, fs, cw=cw
            )
            if use_prod_grid:
                col_l_draw = _col_l
                _mul_draw_product_on_digit_grid(
                    product_display,
                    col_l_draw,
                    prod_y,
                    col_x,
                    cw,
                    parts,
                    ff,
                    pfs,
                    c_main,
                    decimal_fill=c_red,
                    st=st,
                )
                _mul_strike_trailing_fractional_zeros_grid(
                    product_display, col_l_draw, prod_y, col_x, cw, st, parts, pfs, c_red
                )
            else:
                grid_right = margin + Wp * cw
                _mul_text_right(product_display, grid_right, prod_y, st, parts, ff, pfs, c_main)
                _mul_strike_trailing_fractional_zeros(product_display, grid_right, prod_y, st, parts, ff, pfs, c_red)
        m_ext = margin * 0.35
        ink_mul_right = block_right + m_ext
        if omit_redundant_partial_row:
            if not use_prod_grid:
                ink_mul_right = max(ink_mul_right, margin + Wp * cw)
        else:
            ink_mul_right = max(ink_mul_right, line2_x2)
            if not use_prod_grid:
                ink_mul_right = max(ink_mul_right, margin + Wp * cw)
        y = prod_y + fs * 1.12
        verify_digit_grid_cols = W_eff
        total_w = max(margin * 2 + W_eff * cw, block_right + margin * 1.5)
        total_h = y + margin
    elif int_layout is not None:
        W0 = int_layout.width
        grid_right = margin + W0 * cw
        col_range = (
            _verify_product_col_range(product_display, W0, product_decimal_shift)
            if product_decimal_shift is not None
            else None
        )
        # 内层列宽 W0 可能窄于「点小数后」横式积所需列数，col_l 会为负而退回 _mul_text_right（全黑），
        # 丢失左移补位红 0（如 0.016×3 → 0.048 需 W≥4）。
        if col_range is None and product_decimal_shift is not None and "." in product_display:
            ip_w, fp_w = product_display.split(".", 1)
            nd_w = len(ip_w) + len(fp_w)
            need_w = max(W0, nd_w - max(0, len(fp_w) - product_decimal_shift))
            col_range = _verify_product_col_range(
                product_display, need_w, product_decimal_shift
            )
        if col_range is not None:
            col_l, col_r = col_range
            W_eff = max(W0, col_r + 1)
        else:
            col_l = -1
            W_eff = W0
        inner_shift, lead_pad_digits = _mul_verify_product_align_meta(
            int_layout, product_display
        )
        if inner_shift:
            W_eff = max(
                W_eff,
                _school_mul_layout_max_digit_col(int_layout) + inner_shift + 1,
            )
        top_pos = _strip_verify_row_pos_col(
            factor_top_display, int_layout.top, lambda c: c, inner_shift
        )
        bot_pos = _strip_verify_row_pos_col(
            factor_bot_display, int_layout.bot, lambda c: c, inner_shift
        )
        if top_pos is not None or bot_pos is not None:
            s_max = 0
            for pc in (top_pos, bot_pos):
                if pc:
                    s_max = max(s_max, max(pc.values(), default=0))
            W_eff = max(W_eff, s_max + 1)
        known_ns = _verify_mul_known_from_pos(
            W_eff, st, margin, factor_top_display, factor_bot_display, top_pos, bot_pos
        )
        if known_ns:
            col_x = _col_x_from_known_columns(W_eff, known_ns, margin, cw)
        else:
            col_x = [margin + (i + 0.5) * cw for i in range(W_eff)]
        block_right = col_x[-1] + 0.5 * cw if W_eff > 0 else margin
        y = margin + fs * 0.35
        gap_rule1 = max(fs * 0.72, gap_below_rule)

        # 与 strip 验算相同：前导/末尾 0 与横式小数点仍映射到内层 DigitRow 列；勿用 _mul_text_right（小数点宽 0.32cw
        # 与数字 cw 混排会导致上下因子与竖式列错位，如 0.032×25.6）。
        use_factor_grid = False
        rule_line_left = 2.0
        if top_pos is not None and bot_pos is not None:
            buf: list[str] = []
            y_top = y
            if _append_strip_verify_factor_row_parts(
                factor_top_display,
                top_pos,
                col_x,
                y_top,
                st,
                buf,
                ff,
                fs,
                c_main,
            ):
                y_mid = y_top + row_h
                min_dc_times = max(0, min(min(top_pos.values()), min(bot_pos.values())))
                x_times, rule_line_left = _verify_times_center_and_rule_x1(
                    col_x, cw, margin, min_dc_times, fs
                )
                buf.append(
                    _text(x_times, y_mid, "×", anchor="middle", fs=fs, fill=c_main, font_family=ff)
                )
                if _append_strip_verify_factor_row_parts(
                    factor_bot_display,
                    bot_pos,
                    col_x,
                    y_mid,
                    st,
                    buf,
                    ff,
                    fs,
                    c_main,
                ):
                    parts.extend(buf)
                    use_factor_grid = True
        if not use_factor_grid:
            _mul_text_right(factor_top_display, grid_right, y, st, parts, ff, fs, c_main)
        y += row_h
        if not use_factor_grid:
            bot_w = _mul_row_text_width(factor_bot_display, st)
            bot_left = grid_right - bot_w
            x_times = bot_left - cw * _MUL_VERIFY_TIMES_OFFSET_CW
            if x_times < margin * _MUL_VERIFY_TIMES_MIN_X_MARGIN:
                x_times = margin * _MUL_VERIFY_TIMES_MIN_X_MARGIN
            parts.append(_text(x_times, y, "×", anchor="middle", fs=fs, fill=c_main, font_family=ff))
            _mul_text_right(factor_bot_display, grid_right, y, st, parts, ff, fs, c_main)
            sym_hw_fb = _glyph_half_width_times_or_plus(fs, cw)
            rule_line_left = max(2.0, x_times - sym_hw_fb - _SYM_RULE_GAP_PX)
        y += row_h * rule1_after
        line1_y = y
        parts.append(
            f'<line x1="{rule_line_left:.2f}" y1="{line1_y:.2f}" x2="{block_right + margin * 0.35:.2f}" y2="{line1_y:.2f}" '
            f'stroke="{c_main}" stroke-width="1.65" stroke-linecap="round"/>'
        )
        n_partials = len(int_layout.partial_rows)
        omit_single_partial = n_partials == 1 and not int_layout.sum_carry
        pfs = fs * 0.95
        use_prod_grid = col_range is not None
        if omit_single_partial:
            carries0, _prow0 = int_layout.partial_rows[0]
            y_first_carry = line1_y - _MUL_FIRST_ROW_CARRY_ABOVE_RULE_PX
            _mul_draw_carries(
                carries0,
                col_x,
                line1_y,
                st,
                parts,
                ff,
                fs,
                cw=cw,
                y_center_direct=y_first_carry,
                col_shift=inner_shift,
            )
            gap_prod_below_rule1 = max(fs * 0.72, gap_rule1 * 0.98)
            prod_y = line1_y + gap_prod_below_rule1
            if use_prod_grid:
                _mul_draw_product_on_digit_grid(
                    product_display,
                    col_l,
                    prod_y,
                    col_x,
                    cw,
                    parts,
                    ff,
                    pfs,
                    c_main,
                    decimal_fill=c_red,
                    lead_pad_digit_count=lead_pad_digits,
                    st=st,
                )
                _mul_strike_trailing_fractional_zeros_grid(
                    product_display, col_l, prod_y, col_x, cw, st, parts, pfs, c_red
                )
            else:
                _mul_text_right(product_display, grid_right, prod_y, st, parts, ff, pfs, c_main)
                _mul_strike_trailing_fractional_zeros(
                    product_display, grid_right, prod_y, st, parts, ff, pfs, c_red
                )
        else:
            y_digit = line1_y + gap_rule1
            y_digit_prev = line1_y
            partials_for_rule2: list[tuple[list[CarryDigit], DigitRow]] = []
            for idx, (carries, prow) in enumerate(int_layout.partial_rows):
                partials_for_rule2.append((carries, prow))
                if idx == 0:
                    y_first_carry = line1_y - _MUL_FIRST_ROW_CARRY_ABOVE_RULE_PX
                    _mul_draw_carries(
                        carries,
                        col_x,
                        line1_y,
                        st,
                        parts,
                        ff,
                        fs,
                        cw=cw,
                        y_center_direct=y_first_carry,
                        col_shift=inner_shift,
                    )
                else:
                    y_carry = _mul_carry_y_between_partial_rows(y_digit_prev, y_digit, fs)
                    _mul_draw_carries(
                        carries,
                        col_x,
                        y_carry,
                        st,
                        parts,
                        ff,
                        fs,
                        cw=cw,
                        col_shift=inner_shift,
                    )
                _mul_digit_row_cells(
                    prow, col_x, y_digit, st, parts, ff, fs, c_main, col_shift=inner_shift
                )
                y_digit_prev = y_digit
                if idx < n_partials - 1:
                    y_digit += row_gap_partial
            line2_y = y_digit + fs * 0.34
            rule_x2_main = block_right + margin * 0.35
            prod_rng_main = (col_l, col_r) if use_prod_grid and col_range is not None else None
            line2_x1, line2_x2 = _mul_second_rule_line_x1_x2(
                col_x=col_x,
                cw=cw,
                fs=fs,
                rule_x1=rule_line_left,
                rule_x2=rule_x2_main,
                partial_rows=partials_for_rule2,
                product_col_range=prod_rng_main,
                layout_col_shift=inner_shift,
            )
            parts.append(
                f'<line x1="{line2_x1:.2f}" y1="{line2_y:.2f}" x2="{line2_x2:.2f}" y2="{line2_y:.2f}" '
                f'stroke="{c_main}" stroke-width="1.65" stroke-linecap="round"/>'
            )
            gap_prod_below_rule2 = max(fs * 0.74, gap_below_rule * (1.02 if int_layout.sum_carry else 0.96))
            prod_y = line2_y + gap_prod_below_rule2
            if int_layout.sum_carry:
                y_sc = _mul_carry_y_between_rule2_and_product(line2_y, prod_y, fs)
                _mul_draw_carries(
                    int_layout.sum_carry,
                    col_x,
                    y_sc,
                    st,
                    parts,
                    ff,
                    fs,
                    cw=cw,
                    col_shift=inner_shift,
                )
            if use_prod_grid:
                _mul_draw_product_on_digit_grid(
                    product_display,
                    col_l,
                    prod_y,
                    col_x,
                    cw,
                    parts,
                    ff,
                    pfs,
                    c_main,
                    decimal_fill=c_red,
                    lead_pad_digit_count=lead_pad_digits,
                    st=st,
                )
                _mul_strike_trailing_fractional_zeros_grid(
                    product_display, col_l, prod_y, col_x, cw, st, parts, pfs, c_red
                )
            else:
                _mul_text_right(product_display, grid_right, prod_y, st, parts, ff, pfs, c_main)
                _mul_strike_trailing_fractional_zeros(product_display, grid_right, prod_y, st, parts, ff, pfs, c_red)
        m_ext2 = margin * 0.35
        ink_mul_right = block_right + m_ext2
        if not omit_single_partial:
            ink_mul_right = max(ink_mul_right, line2_x2)
        if not use_prod_grid:
            ink_mul_right = max(ink_mul_right, grid_right)
        y = prod_y + fs * 1.12
        verify_digit_grid_cols = W_eff
        total_w = max(margin * 2 + W_eff * cw, block_right + margin * 1.5)
        total_h = y + margin
    else:
        lines = [factor_top_display, factor_bot_display, product_display]
        max_tw = max(_mul_row_text_width(ln, st) for ln in lines) + cw * 2
        block_right = margin + max_tw
        y = margin + fs * 0.35
        for i, ln in enumerate(lines):
            if i == 1:
                bot_w = _mul_row_text_width(ln, st)
                bot_left = block_right - bot_w
                x_times = bot_left - cw * _MUL_VERIFY_TIMES_OFFSET_CW
                if x_times < margin * _MUL_VERIFY_TIMES_MIN_X_MARGIN:
                    x_times = margin * _MUL_VERIFY_TIMES_MIN_X_MARGIN
                parts.append(_text(x_times, y, "×", anchor="middle", fs=fs, fill=c_main, font_family=ff))
            _mul_text_right(ln, block_right, y, st, parts, ff, fs, c_main)
            y += row_h
        total_w = block_right + margin
        prod_line_y = y - row_h
        _mul_strike_trailing_fractional_zeros(
            product_display, block_right, prod_line_y, st, parts, ff, fs, c_red
        )
        total_h = y + margin
        ink_mul_right = block_right

    inner = "\n".join(parts)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.1f}" height="{total_h:.1f}" '
        f'viewBox="0 0 {total_w:.1f} {total_h:.1f}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        f"{_latin_modern_defs()}"
        f"{inner}</svg>"
    )
    return svg, total_w, total_h, verify_digit_grid_cols, ink_mul_right


def render_multiplication_check_svg(
    *,
    factor_top: str,
    factor_bottom: str,
    product_display: str,
    label: str = "验算：",
    st: Style | None = None,
) -> str:
    """兼容旧接口：无整数竖式布局时走简化右对齐三行。"""
    svg, _w, _h, _, _ = render_verification_multiplication_svg(
        factor_top_display=factor_top,
        factor_bot_display=factor_bottom,
        product_display=product_display,
        int_layout=None,
        st=st,
    )
    return svg


def _column_op_col_x(w: int, margin: float, cw: float) -> list[float]:
    return [margin + (i + 0.5) * cw for i in range(w)]


def _column_op_min_used_col(rows: list[DigitRow]) -> int:
    cols = [c for r in rows for c in r.cells]
    return min(cols) if cols else 0


def addition_layout_ink_right_x(layout: AdditionLayout, st: Style | None = None) -> float:
    """与 `render_addition_vertical_svg` 中结果横线 `x2` 一致，用于与主竖式墨迹右缘对齐。"""
    st = st or Style()
    fs = st.font_size
    margin_left = 16.0
    cw = st.cell_w
    w = layout.width
    min_col_all = _column_op_min_used_col([layout.top, layout.bot])
    col_x: list[float] = []
    rule_x0 = 2.0
    for _ in range(12):
        col_x = [margin_left + (i + 0.5) * cw for i in range(w)]
        _x_plus, rule_x0 = _add_sub_symbol_x_and_rule_x0(col_x, cw, min_col_all, fs)
        if rule_x0 >= 2.0:
            break
        margin_left += max(2.0 - rule_x0, 4.0)
    return col_x[w - 1] + cw * 0.48


def render_addition_vertical_svg(
    layout: AdditionLayout,
    *,
    horizontal_line: str = "",
    st: Style | None = None,
) -> str:
    """整数加法竖式（进位色见 `render_config`）；横式可选。"""
    st = st or Style()
    fs = st.font_size
    c_main = st.color_main
    ff = st.font_family
    margin_right = 16.0
    margin_left = 16.0
    cw = st.cell_w
    w = layout.width
    min_col_all = _column_op_min_used_col([layout.top, layout.bot])
    col_x: list[float] = []
    x_plus = 0.0
    rule_x0 = 2.0
    for _ in range(12):
        col_x = [margin_left + (i + 0.5) * cw for i in range(w)]
        x_plus, rule_x0 = _add_sub_symbol_x_and_rule_x0(col_x, cw, min_col_all, fs)
        if rule_x0 >= 2.0:
            break
        margin_left += max(2.0 - rule_x0, 4.0)
    gap_rule = fs * 0.50
    gap_after_rule = fs * 0.64
    row_step = fs * 1.08
    parts: list[str] = []
    y = margin_right + fs * 0.35
    if horizontal_line and horizontal_line.strip():
        parts.append(
            _text(margin_left + (w * cw) / 2, y, horizontal_line, anchor="middle", fs=fs + 1, fill=c_main, font_family=ff)
        )
        y += row_step * 0.95
    y_top = y + fs * 0.2
    y_carry_band = y_top - fs * 0.28
    _mul_draw_carries(layout.carries, col_x, y_carry_band, st, parts, ff, fs, cw=cw)
    _mul_digit_row_cells(layout.top, col_x, y_top, st, parts, ff, fs, c_main)
    y_bot = y_top + row_step
    parts.append(_text(x_plus, y_bot, "+", anchor="middle", fs=fs, fill=c_main, font_family=ff))
    _mul_digit_row_cells(layout.bot, col_x, y_bot, st, parts, ff, fs, c_main)
    line_y = y_bot + gap_rule
    x1 = col_x[w - 1] + cw * 0.48
    parts.append(
        f'<line x1="{rule_x0:.2f}" y1="{line_y:.2f}" x2="{x1:.2f}" y2="{line_y:.2f}" '
        f'stroke="{c_main}" stroke-width="1.75"/>'
    )
    y_sum = line_y + gap_after_rule
    _mul_digit_row_cells(layout.sum_row, col_x, y_sum, st, parts, ff, fs, c_main)
    total_w = margin_left + w * cw + margin_right
    total_h = y_sum + fs * 0.85 + margin_right
    inner = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.1f}" height="{total_h:.1f}" '
        f'viewBox="0 0 {total_w:.1f} {total_h:.1f}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        f"{_latin_modern_defs()}"
        f"{inner}</svg>"
    )


def render_subtraction_vertical_svg(
    layout: SubtractionLayout,
    *,
    horizontal_line: str = "",
    st: Style | None = None,
) -> str:
    """整数减法竖式（借位色见 `render_config`）。"""
    st = st or Style()
    fs = st.font_size
    c_main = st.color_main
    ff = st.font_family
    margin_right = 16.0
    margin_left = 16.0
    cw = st.cell_w
    w = layout.width
    min_col_all = _column_op_min_used_col([layout.top, layout.bot])
    col_x: list[float] = []
    x_minus = 0.0
    rule_x0 = 2.0
    for _ in range(12):
        col_x = [margin_left + (i + 0.5) * cw for i in range(w)]
        x_minus, rule_x0 = _add_sub_symbol_x_and_rule_x0(col_x, cw, min_col_all, fs)
        if rule_x0 >= 2.0:
            break
        margin_left += max(2.0 - rule_x0, 4.0)
    gap_rule = fs * 0.50
    gap_after_rule = fs * 0.64
    row_step = fs * 1.08
    parts: list[str] = []
    y = margin_right + fs * 0.35
    if horizontal_line and horizontal_line.strip():
        parts.append(
            _text(margin_left + (w * cw) / 2, y, horizontal_line, anchor="middle", fs=fs + 1, fill=c_main, font_family=ff)
        )
        y += row_step * 0.95
    y_top = y + fs * 0.2
    y_borrow = y_top - fs * 0.32
    _mul_draw_carries(layout.borrows, col_x, y_borrow, st, parts, ff, fs, cw=cw)
    _mul_digit_row_cells(layout.top, col_x, y_top, st, parts, ff, fs, c_main)
    y_bot = y_top + row_step
    parts.append(_text(x_minus, y_bot, "−", anchor="middle", fs=fs, fill=c_main, font_family=ff))
    _mul_digit_row_cells(layout.bot, col_x, y_bot, st, parts, ff, fs, c_main)
    line_y = y_bot + gap_rule
    x1 = col_x[w - 1] + cw * 0.48
    parts.append(
        f'<line x1="{rule_x0:.2f}" y1="{line_y:.2f}" x2="{x1:.2f}" y2="{line_y:.2f}" '
        f'stroke="{c_main}" stroke-width="1.75"/>'
    )
    y_diff = line_y + gap_after_rule
    _mul_digit_row_cells(layout.diff_row, col_x, y_diff, st, parts, ff, fs, c_main)
    total_w = margin_left + w * cw + margin_right
    total_h = y_diff + fs * 0.85 + margin_right
    inner = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.1f}" height="{total_h:.1f}" '
        f'viewBox="0 0 {total_w:.1f} {total_h:.1f}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        f"{_latin_modern_defs()}"
        f"{inner}</svg>"
    )
