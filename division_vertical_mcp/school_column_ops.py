"""教材风格整数加/减竖式布局（数位对齐、进位/借位列），供 SVG 渲染。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .school_multiply import CarryDigit, DigitRow, _place_row


def _norm_nonneg_int_str(s: str) -> str:
    s = s.strip().replace(" ", "").replace(",", "")
    if not s or not s.isdigit():
        raise ValueError("加数/减数须为非负整数字符串")
    t = s.lstrip("0") or "0"
    return t


def normalize_nonneg_integer_operand(s: str) -> str:
    """对外：规范非负整数字符串（去空格逗号、去多余前导零）。"""
    return _norm_nonneg_int_str(s)


@dataclass
class AdditionLayout:
    width: int
    top: DigitRow
    bot: DigitRow
    carries: list[CarryDigit] = field(default_factory=list)
    sum_row: DigitRow = field(default_factory=lambda: DigitRow({}))


@dataclass
class SubtractionLayout:
    width: int
    top: DigitRow
    bot: DigitRow
    borrows: list[CarryDigit]
    diff_row: DigitRow


def layout_integer_addition(
    addend_top: str, addend_bot: str, *, grid_width: int | None = None
) -> AdditionLayout:
    """两非负整数相加，右端对齐；红色进位标在左侧相邻列上方。

    grid_width：可选，与配对竖式（如验算乘法）的列网格宽度一致时使用，使上下块个位列对齐；
    实际宽度取 max(grid_width, 本运算所需最小列数)。
    """
    a = _norm_nonneg_int_str(addend_top)
    b = _norm_nonneg_int_str(addend_bot)
    L = max(len(a), len(b))
    sum_s = str(int(a) + int(b))
    w_min = max(L + 1, len(sum_s))
    if grid_width is None:
        w = L + 3
    else:
        w = max(int(grid_width), w_min)
    top = _place_row(a, w - 1, w)
    bot = _place_row(b, w - 1, w)
    carries: list[CarryDigit] = []
    c = 0
    sum_cells: dict[int, str] = {}
    for col in range(w - 1, -1, -1):
        da = int(top.cells[col]) if col in top.cells else 0
        db = int(bot.cells[col]) if col in bot.cells else 0
        tot = da + db + c
        sum_cells[col] = str(tot % 10)
        c = tot // 10
        if c and col > 0:
            carries.append(CarryDigit(col=col - 1, ch=str(c), dy=-0.38))
    s_str = "".join(sum_cells[i] for i in range(w)).lstrip("0") or "0"
    sum_row = _place_row(s_str, w - 1, w)
    return AdditionLayout(width=w, top=top, bot=bot, carries=carries, sum_row=sum_row)


def layout_integer_subtraction(minuend: str, subtrahend: str) -> SubtractionLayout:
    """非负大 − 小，右端对齐；借位链用红色小字标出。"""
    a = _norm_nonneg_int_str(minuend)
    b = _norm_nonneg_int_str(subtrahend)
    if int(a) < int(b):
        raise ValueError("被减数须大于等于减数（当前仅支持非负且差非负）")
    L = len(a)
    w = L + 2
    top = _place_row(a, w - 1, w)
    bot = _place_row(b, w - 1, w)
    m = [int(a[i]) for i in range(L)]
    db = [int(b[i]) for i in range(len(b))]
    db_pad = [0] * (L - len(db)) + db
    borrows: list[CarryDigit] = []

    def idx_to_col(i: int) -> int:
        return w - L + i

    for i in range(L - 1, -1, -1):
        if m[i] < db_pad[i]:
            j = i - 1
            while j >= 0 and m[j] == 0:
                m[j] = 9
                borrows.append(CarryDigit(col=idx_to_col(j), ch="1", dy=-0.35))
                j -= 1
            if j < 0:
                raise ValueError("内部错误：借位失败")
            borrows.append(CarryDigit(col=idx_to_col(j), ch="1", dy=-0.35))
            m[j] -= 1
            m[i] += 10
        m[i] -= db_pad[i]

    diff_s = "".join(str(m[i]) for i in range(L)).lstrip("0") or "0"
    diff_row = _place_row(diff_s, w - 1, w)
    return SubtractionLayout(width=w, top=top, bot=bot, borrows=borrows, diff_row=diff_row)
