"""教材风格整数乘法竖式布局（数位对齐 + 进位），供验算 SVG 使用。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CarryDigit:
    """在列 `col` 上、相对行基线 `dy`（负值略偏上）画红色进位数字。"""

    col: int
    ch: str
    dy: float = -0.42


@dataclass
class DigitRow:
    """一行数字，列索引从块左 0 起；`cells[col]=digit`。"""

    cells: dict[int, str]


@dataclass
class SchoolMultiplyLayout:
    """整数 × 整数（仅数字串）竖式：若干部分积行 + 横线 + 和行（含进位）。"""

    width: int
    top: DigitRow
    bot: DigitRow
    partial_rows: list[tuple[list[CarryDigit], DigitRow]] = field(default_factory=list)
    sum_carry: list[CarryDigit] = field(default_factory=list)
    sum_row: DigitRow = field(default_factory=lambda: DigitRow({}))


def _digits(s: str) -> list[int]:
    if not s.isdigit():
        raise ValueError("school_multiply 仅支持非负整数字符串")
    return [int(c) for c in s]


def _place_row(s: str, right_col: int, w: int) -> DigitRow:
    cells: dict[int, str] = {}
    for i, ch in enumerate(s):
        col = right_col - (len(s) - 1 - i)
        if 0 <= col < w:
            cells[col] = ch
    return DigitRow(cells)


def _partial_mult_carries(da: list[int], d: int, right_col: int, w: int) -> tuple[list[CarryDigit], DigitRow]:
    """ta×一位 d：返回进位标注 + 部分积行（右端对齐 right_col）。"""
    carries: list[CarryDigit] = []
    out_rev: list[int] = []
    c = 0
    for i in range(len(da) - 1, -1, -1):
        s = da[i] * d + c
        out_rev.append(s % 10)
        c = s // 10
        if c:
            prod_right = right_col - (len(da) - 1 - i)
            cc = prod_right - 1
            if 0 <= cc < w:
                carries.append(CarryDigit(col=cc, ch=str(c)))
    if c:
        out_rev.append(c)
    out_rev.reverse()
    ps = "".join(str(x) for x in out_rev)
    return carries, _place_row(ps, right_col, w)


def layout_integer_multiply(ta: str, tb: str) -> SchoolMultiplyLayout:
    """
    ta × tb，均为非负整数字符串（无前导零，可为 \"0\"）。
    列宽 len(ta)+len(tb)；乘数第 j 位（从左 0 起）的部分积右端与乘数该位所在列对齐。
    """
    ta = ta.lstrip("0") or "0"
    tb = tb.lstrip("0") or "0"
    w = len(ta) + len(tb)
    if ta == "0" or tb == "0":
        top = _place_row(ta, w - 1, w)
        bot = _place_row(tb, w - 1, w)
        z = _place_row("0", w - 1, w)
        return SchoolMultiplyLayout(width=w, top=top, bot=bot, partial_rows=[([], z)], sum_row=z)

    da = _digits(ta)
    db = _digits(tb)
    top = _place_row(ta, w - 1, w)
    bot = _place_row(tb, w - 1, w)

    # 自下而上：先乘乘数个位（右），再向左逐位，部分积右端与该位对齐
    partials: list[tuple[list[CarryDigit], DigitRow]] = []
    for k in range(len(db)):
        j = len(db) - 1 - k
        d = db[j]
        right = w - 1 - k
        carries, prow = _partial_mult_carries(da, d, right, w)
        partials.append((carries, prow))

    acc = [0] * w
    for _c, prow in partials:
        for col, ch in prow.cells.items():
            acc[col] += int(ch)

    out = [0] * w
    c = 0
    sum_carries: list[CarryDigit] = []
    for col in range(w - 1, -1, -1):
        s = acc[col] + c
        out[col] = s % 10
        c = s // 10
        if c and col > 0:
            sum_carries.append(CarryDigit(col=col - 1, ch=str(c)))
    if c:
        sum_carries.append(CarryDigit(col=-1, ch=str(c)))
    s_str = "".join(str(out[i]) for i in range(w)).lstrip("0") or "0"
    sum_row = _place_row(s_str, w - 1, w)

    return SchoolMultiplyLayout(
        width=w,
        top=top,
        bot=bot,
        partial_rows=partials,
        sum_carry=sum_carries,
        sum_row=sum_row,
    )
