from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext

getcontext().prec = 80


def _normalize_decimal_str(s: str) -> str:
    s = s.strip().replace(" ", "").replace(",", "")
    if not s:
        raise ValueError("空字符串")
    if s.count(".") > 1:
        raise ValueError("只能有一个小数点")
    return s


def strip_trailing_frac_zeros_from_f_str(s: str) -> str:
    """`format(Decimal, \"f\")` 的串：只去掉小数点后的尾随 0 及孤立小数点。

    无小数点时原样返回，避免 `100`.rstrip(\"0\") → `1` 这类错误。
    """
    if "." not in s:
        return s
    t = s.rstrip("0").rstrip(".")
    return t if t else "0"


def _decimal_fraction_places(x: Decimal) -> int:
    """有限小数输入下，使 x·10^k 为整数所需的最小 k（与 Decimal 指数一致）。"""
    e = x.as_tuple().exponent
    return max(0, -int(e))


def decimal_to_scaled_ints(dividend: str, divisor: str) -> tuple[int, int, int, str, str]:
    da = _normalize_decimal_str(dividend)
    db = _normalize_decimal_str(divisor)
    a = Decimal(da)
    b = Decimal(db)
    if b == 0:
        raise ValueError("除数不能为 0")
    # 同时去掉被除数、除数的小数点：k 取两者小数位数较大者（例如 8.75÷2.5 须 k≥2）
    k = max(_decimal_fraction_places(a), _decimal_fraction_places(b))
    b_int = int(b * (Decimal(10) ** k))
    a_scaled = a * (Decimal(10) ** k)
    if a_scaled != a_scaled.to_integral_value():
        raise ValueError("被除数在移位后不是有限整数；请调整输入或使用更高精度")
    d_int = int(a_scaled)
    return d_int, b_int, k, db, da


@dataclass
class ShiftMarks:
    """教学留痕（由 compose 对所有题目统一构造，svg_render 只负责按字段绘制）：
    除数：整数部分前导 0、小数点、小数部分前连续占位 0（如 0.016 的 0.0）短划；被除数：原小数点在两数字正中画红点并短划，移位后新小数点标红；
    或「0.xx 移位为整数」时在原式上划前导 0 与首小数点（见 prefix_*）。"""

    divisor_leading_zero_strikes: int
    # 小数点后、首个非 0 前的连续 0，与「整数部分前导 0 + 小数点」一并划去（如 0.016 的 0.0）
    divisor_fractional_leading_zero_strikes: int
    divisor_dot_strike: bool
    dividend_dot_strike: bool
    # 原小数点在移位后串中的位置：划在「第 gap 个数字」与「第 gap+1 个数字」之间（数字不含小数点字符，从左 0 起）
    dividend_old_decimal_gap_after_digit: int | None = None
    # 被除数行里第几个 cell 是小数点，用红色绘制（移位后的新小数点）
    dividend_new_decimal_cell_index: int | None = None
    # 被除数「原式补零」时：这些 cell 上的 0 用前导零短划；这些 cell 上的 . 用小点短划
    dividend_prefix_zero_strike_cells: list[int] = field(default_factory=list)
    dividend_prefix_dot_strike_cells: list[int] = field(default_factory=list)
    # 整数被除数续除时在竖式中补的小数点后的 0（如 1÷4 → 1.00）：与 dividend_new_decimal_cell_index 同色标红
    dividend_extension_red_digit_cells: list[int] = field(default_factory=list)


def _divisor_leading_zeros_before_dot(full: str) -> int:
    """从串首起连续 '0'，遇 '.' 或非 '0' 数字即停（不划有效数位）。"""
    n = 0
    for ch in full:
        if ch == "0":
            n += 1
        elif ch == ".":
            break
        else:
            break
    return n


def _divisor_leading_fractional_zeros_after_dot(full: str) -> int:
    """小数点后、第一个非 0 数字前的连续占位 0（如 0.016 里小数点后的第一个 0）。"""
    if "." not in full:
        return 0
    _ip, fp = full.split(".", 1)
    n = 0
    for ch in fp:
        if ch == "0":
            n += 1
        else:
            break
    return n


def compute_shift_marks(
    divisor_orig: str,
    dividend_orig: str,
    display_shift_k: int,
    *,
    dividend_old_decimal_gap_after_digit: int | None = None,
    dividend_new_decimal_cell_index: int | None = None,
    dividend_prefix_zero_strike_cells: list[int] | None = None,
    dividend_prefix_dot_strike_cells: list[int] | None = None,
    dividend_extension_red_digit_cells: list[int] | None = None,
) -> ShiftMarks:
    """与 `compose.build_combined_svg` 配套；任意被除数/除数字符串均走同一套规则。"""
    full = _normalize_decimal_str(divisor_orig)
    dvd = _normalize_decimal_str(dividend_orig)
    lead = _divisor_leading_zeros_before_dot(full)
    frac_lead = _divisor_leading_fractional_zeros_after_dot(full) if display_shift_k > 0 else 0
    # display_shift_k：与竖式中除数小数点右移位数一致（通常取除数小数位数）
    dot = "." in full and display_shift_k > 0
    pz = list(dividend_prefix_zero_strike_cells or [])
    pd = list(dividend_prefix_dot_strike_cells or [])
    # 若已用「原位置红点 + 短划」或 prefix 划法，则不再对 dividend 的某个 '.' 走 dividend_dot_strike
    dot_strike = ("." in dvd) and (dividend_old_decimal_gap_after_digit is None) and not pz and not pd
    return ShiftMarks(
        divisor_leading_zero_strikes=lead,
        divisor_fractional_leading_zero_strikes=frac_lead,
        divisor_dot_strike=dot,
        dividend_dot_strike=dot_strike,
        dividend_old_decimal_gap_after_digit=dividend_old_decimal_gap_after_digit,
        dividend_new_decimal_cell_index=dividend_new_decimal_cell_index,
        dividend_prefix_zero_strike_cells=pz,
        dividend_prefix_dot_strike_cells=pd,
        dividend_extension_red_digit_cells=list(dividend_extension_red_digit_cells or []),
    )


def divisor_fraction_shift_k(divisor: Decimal) -> int:
    return _decimal_fraction_places(divisor)


def scaled_dividend_digits_for_divisor_shift(dividend: Decimal, divisor: Decimal) -> tuple[str, int, int, int]:
    """
    按「除数小数点右移 k 位变整数」同步右移被除数，得到仅数字串 ds 与小数点位置 dec_after。
    返回 (ds, dec_after, k_div, divisor_int)。
    """
    k = divisor_fraction_shift_k(divisor)
    x = dividend * (Decimal(10) ** k)
    if x != x.to_integral_value():
        s = strip_trailing_frac_zeros_from_f_str(format(x, "f"))
        if "." not in s:
            ds, dec_after = s, len(s)
        else:
            ip, fp = s.split(".", 1)
            ds = ip + fp
            dec_after = len(ip)
    else:
        ds = str(int(x))
        dec_after = len(ds)
    b_int = int(divisor * (Decimal(10) ** k))
    return ds, dec_after, k, b_int
