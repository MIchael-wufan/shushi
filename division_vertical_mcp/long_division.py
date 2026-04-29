from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .decimal_math import strip_trailing_frac_zeros_from_f_str


@dataclass
class DivisionStep:
    partial: int
    quotient_digit: str
    product: int
    partial_start_col: int
    partial_end_col: int
    remainder_after: int = 0  # 该步乘积减后余数（教材竖式横线下方一行）


@dataclass
class LongDivisionLayout:
    scaled_dividend: str
    scaled_divisor: str
    quotient: str
    quotient_slots: list[tuple[int, str]]
    steps: list[DivisionStep]
    final_remainder: int
    quotient_frac_slots: list[tuple[int, str]] = field(default_factory=list)
    has_quotient_decimal_point: bool = False
    # 仅数字的 scaled_dividend 中，小数点位于第 dec_after 位数字之前（87.5 → ds=875, dec_after=2）
    dividend_dec_after: int | None = None
    # 无限循环小数：在 quotient_frac_slots 中该下标数字上方画红点（与横式 COMBINING DOT ABOVE 一致）
    quotient_recurring_dot_frac_slot_index: int | None = None


def long_division_layout(dividend: int, divisor: int) -> LongDivisionLayout:
    """
    教材竖式：每次只商一位（0–9），先逐位吃入被除数直至部分余数 >= 除数，再减；
    与整数 D // divisor 的整数商、余数一致（商字符串为去前导零的整数部分）。
    """
    if divisor <= 0:
        raise ValueError("除数须为正整数")
    ds = str(dividend)
    n = len(ds)
    i = 0
    rem = 0
    quotient_slots: list[tuple[int, str]] = []
    steps: list[DivisionStep] = []

    while i < n:
        rem = rem * 10 + int(ds[i])
        i += 1
        if rem >= divisor:
            break
        quotient_slots.append((i - 1, "0"))
    else:
        return LongDivisionLayout(
            scaled_dividend=ds,
            scaled_divisor=str(divisor),
            quotient="0",
            quotient_slots=quotient_slots,
            steps=[],
            final_remainder=rem,
            dividend_dec_after=len(ds),
            quotient_recurring_dot_frac_slot_index=None,
        )

    while True:
        q = rem // divisor
        if q > 9:
            raise ValueError("内部错误：商位大于 9，请检查输入")
        prod = q * divisor
        end_col = i - 1
        # 部分积横跨的数位列：与「当前部分余数 rem」位数一致（如 125 对齐三列）
        psc = end_col - (len(str(rem)) - 1)
        if psc < 0:
            psc = 0
        rem_after = rem - prod
        steps.append(
            DivisionStep(
                partial=rem,
                quotient_digit=str(q),
                product=prod,
                partial_start_col=psc,
                partial_end_col=end_col,
                remainder_after=rem_after,
            )
        )
        quotient_slots.append((end_col, str(q)))
        rem = rem_after

        if i >= n and rem == 0:
            break
        if i >= n:
            break

        while i < n:
            rem = rem * 10 + int(ds[i])
            i += 1
            if rem >= divisor:
                break
            quotient_slots.append((i - 1, "0"))

        if rem == 0 and i >= n:
            break
        if i >= n and rem < divisor:  # 数位耗尽且不够再除，rem 为最终余数，无需再商一位
            break

    qraw = "".join(d for _, d in quotient_slots)
    if int(qraw) != dividend // divisor or rem != dividend % divisor:
        raise ValueError("内部错误：竖式商与整数除法不一致")
    qnorm = qraw.lstrip("0") or "0"
    return LongDivisionLayout(
        scaled_dividend=ds,
        scaled_divisor=str(divisor),
        quotient=qnorm,
        quotient_slots=quotient_slots,
        steps=steps,
        final_remainder=rem,
        dividend_dec_after=len(ds),
        quotient_recurring_dot_frac_slot_index=None,
    )


def _digit_string_decimal_value(ds: str, dec_after: int) -> Decimal:
    if dec_after >= len(ds):
        return Decimal(int(ds)) if ds else Decimal(0)
    return Decimal(ds[:dec_after] + "." + ds[dec_after:])


def _strip_leading_quotient_slots(slots: list[tuple[int, str]]) -> list[tuple[int, str]]:
    if not slots:
        return []
    for i, (_c, d) in enumerate(slots):
        if d != "0":
            return slots[i:]
    return [slots[-1]]


def _split_slots_by_exact_quotient(
    quotient_slots: list[tuple[int, str]], exact: Decimal, divisor: int
) -> tuple[list[tuple[int, str]], list[tuple[int, str]], bool, str]:
    qtxt = strip_trailing_frac_zeros_from_f_str(format(exact, "f"))
    has_dot = "." in qtxt
    if has_dot:
        ip, _fp = qtxt.split(".", 1)
        ip_st = ip.lstrip("0")
        n_int = len(ip_st) if ip_st else 0
    else:
        ip = qtxt
        ip_st = ip.lstrip("0") or "0"
        n_int = len(ip_st)
    ss = _strip_leading_quotient_slots(quotient_slots)
    qdigits = qtxt.replace(".", "")
    if len(ss) != len(qdigits):
        raise ValueError("内部错误：竖式商位与精确商数字个数不一致")
    if not has_dot:
        return ss, [], False, qtxt
    int_slots = ss[:n_int]
    frac_slots = ss[n_int:]
    return int_slots, frac_slots, True, qtxt


def long_division_layout_embedded(ds: str, dec_after: int, divisor: int) -> LongDivisionLayout:
    """
    被除数以仅数字串 ds + 小数位 dec_after 表示（如 87.5 → ds='875', dec_after=2），除数为正整数。
    竖式步骤与教材一致：逐位落下，每步只商一位。
    """
    if divisor <= 0:
        raise ValueError("除数须为正整数")
    n = len(ds)
    if not (0 <= dec_after <= n):
        raise ValueError("dec_after 越界")
    if dec_after == n:
        lo = long_division_layout(int(ds), divisor)
        return LongDivisionLayout(
            scaled_dividend=lo.scaled_dividend,
            scaled_divisor=lo.scaled_divisor,
            quotient=lo.quotient,
            quotient_slots=lo.quotient_slots,
            steps=lo.steps,
            final_remainder=lo.final_remainder,
            quotient_frac_slots=lo.quotient_frac_slots,
            has_quotient_decimal_point=lo.has_quotient_decimal_point,
            dividend_dec_after=len(ds),
            quotient_recurring_dot_frac_slot_index=lo.quotient_recurring_dot_frac_slot_index,
        )

    i = 0
    rem = 0
    quotient_slots: list[tuple[int, str]] = []
    steps: list[DivisionStep] = []

    while i < n:
        rem = rem * 10 + int(ds[i])
        i += 1
        if rem >= divisor:
            break
        quotient_slots.append((i - 1, "0"))
    else:
        return LongDivisionLayout(
            scaled_dividend=ds,
            scaled_divisor=str(divisor),
            quotient="0",
            quotient_slots=quotient_slots,
            steps=[],
            final_remainder=rem,
            dividend_dec_after=dec_after,
            quotient_recurring_dot_frac_slot_index=None,
        )

    while True:
        q = rem // divisor
        if q > 9:
            raise ValueError("内部错误：商位大于 9，请检查输入")
        prod = q * divisor
        end_col = i - 1
        psc = end_col - (len(str(rem)) - 1)
        if psc < 0:
            psc = 0
        rem_after = rem - prod
        steps.append(
            DivisionStep(
                partial=rem,
                quotient_digit=str(q),
                product=prod,
                partial_start_col=psc,
                partial_end_col=end_col,
                remainder_after=rem_after,
            )
        )
        quotient_slots.append((end_col, str(q)))
        rem = rem_after

        if i >= n and rem == 0:
            break
        if i >= n:
            break

        while i < n:
            rem = rem * 10 + int(ds[i])
            i += 1
            if rem >= divisor:
                break
            quotient_slots.append((i - 1, "0"))

        if rem == 0 and i >= n:
            break

    exact = _digit_string_decimal_value(ds, dec_after) / Decimal(divisor)
    int_slots, frac_slots, has_dot, qdisp = _split_slots_by_exact_quotient(quotient_slots, exact, divisor)
    return LongDivisionLayout(
        scaled_dividend=ds,
        scaled_divisor=str(divisor),
        quotient=qdisp,
        quotient_slots=int_slots,
        steps=steps,
        final_remainder=rem,
        quotient_frac_slots=frac_slots,
        has_quotient_decimal_point=has_dot,
        dividend_dec_after=dec_after,
        quotient_recurring_dot_frac_slot_index=None,
    )


def apply_fractional_quotient_extension(
    base: LongDivisionLayout,
    dividend: int,
    divisor: int,
    max_frac_quotient_digits: int,
) -> LongDivisionLayout:
    """
    在整数竖式之后继续除：补 0 带小数，直到商的小数部分达到 max_frac_quotient_digits 位，
    或余数为 0 提前结束。max_frac_quotient_digits 一般取「保留 n 位小数」时的 n+1。
    """
    if max_frac_quotient_digits <= 0:
        return base
    rem = base.final_remainder
    if rem == 0:
        return base

    n_orig = len(base.scaled_dividend)
    steps = list(base.steps)
    frac_slots: list[tuple[int, str]] = []
    rem_run = rem
    appended = 0

    for j in range(max_frac_quotient_digits):
        rem_run = rem_run * 10
        q = rem_run // divisor
        if q > 9:
            raise ValueError(
                "竖式小数步出现商位大于 9，当前版式不支持；请换算式或关闭 retain_decimal_places"
            )
        prod = q * divisor
        end_col = n_orig + j
        psc = end_col - (len(str(rem_run)) - 1)
        if psc < 0:
            psc = 0
        rem_after = rem_run - prod
        steps.append(
            DivisionStep(
                partial=rem_run,
                quotient_digit=str(q),
                product=prod,
                partial_start_col=psc,
                partial_end_col=end_col,
                remainder_after=rem_after,
            )
        )
        frac_slots.append((end_col, str(q)))
        rem_run = rem_after
        appended += 1
        if rem_run == 0:
            break

    new_ds = base.scaled_dividend + "0" * appended
    frac_str = "".join(d for _, d in frac_slots)
    q_display = base.quotient + "." + frac_str if frac_str else base.quotient
    return LongDivisionLayout(
        scaled_dividend=new_ds,
        scaled_divisor=base.scaled_divisor,
        quotient=q_display,
        quotient_slots=list(base.quotient_slots),
        steps=steps,
        final_remainder=rem_run,
        quotient_frac_slots=frac_slots,
        has_quotient_decimal_point=bool(frac_str),
        dividend_dec_after=base.dividend_dec_after,
        quotient_recurring_dot_frac_slot_index=base.quotient_recurring_dot_frac_slot_index,
    )
