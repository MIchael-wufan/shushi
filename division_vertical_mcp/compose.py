from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from math import gcd

from .decimal_math import (
    ShiftMarks,
    compute_shift_marks,
    decimal_to_scaled_ints,
    scaled_dividend_digits_for_divisor_shift,
    strip_trailing_frac_zeros_from_f_str,
    _normalize_decimal_str,
)
from .long_division import (
    DivisionStep,
    LongDivisionLayout,
    apply_fractional_quotient_extension,
    long_division_layout_embedded,
)
from .school_column_ops import (
    layout_integer_addition,
    layout_integer_subtraction,
    normalize_nonneg_integer_operand,
)
from .school_multiply import DigitRow, SchoolMultiplyLayout, layout_integer_multiply
from .svg_render import (
    Style,
    addition_layout_ink_right_x,
    division_subtraction_ink_right_x,
    render_addition_vertical_svg,
    render_division_svg,
    render_subtraction_vertical_svg,
    render_verification_multiplication_svg,
)


def _should_use_pedagogical_zero_shift_dividend_row(dvd_norm: str, work_ds: str, k_div: int) -> bool:
    """除数有小数位（k_div>0）且整数部分全为 0 时，竖式内用「原横式被除数 + 小数部分右侧补零」与移位工作串对齐。

    用 ip+补零后 fp 的全体数字串之末 len(work_ds) 位必须等于 work_ds（如 0.8192 对齐 8192；0.5/0.2 末位为 50≠5 则不走本路径）。
    不再要求「移位后被除数为整数」（dec_after==len(ds)），否则 0.8192÷0.032 会错误画成 819.2。
    """
    if k_div <= 0 or "." not in dvd_norm:
        return False
    ip, fp = dvd_norm.split(".", 1)
    if ip == "" or not set(ip) <= {"0"}:
        return False
    extra = max(0, len(work_ds) - len(fp))
    fp_pad = fp + ("0" * extra)
    digit_flat = ip + fp_pad
    if len(digit_flat) < len(work_ds):
        return False
    return digit_flat[-len(work_ds) :] == work_ds


def _build_pedagogical_zero_shift_dividend(
    dvd_norm: str, work_ds: str, dec_after: int
) -> tuple[list[str], list[int], list[int], list[int], int | None, list[int]]:
    """原式小数部分右侧补零至与工作串数位一致；必要时插入移位后的新小数点（红）。

    返回 (cells, work_col→cell, zero_strike_cells, dot_strike_cells, dividend_new_decimal_cell_index,
    fp_pad_red_digit_cells)：后者为「仅为对齐 work_ds 而在 fp 右侧补的 0」在被除数行中的下标（与续除补零同色标红，如 0.1→0.10、0.100 中由 0.1 补出的第一个 0）。
    """
    ip, fp = dvd_norm.split(".", 1)
    # 小数部分右侧补零，使「末 len(work_ds) 个数字」与移位工作串对齐（如 0.48→0.480 对齐 480）
    extra = max(0, len(work_ds) - len(fp))
    fp_pad = fp + ("0" * extra)
    cells: list[str] = []
    for ch in ip:
        cells.append(ch)
    cells.append(".")
    for ch in fp_pad:
        cells.append(ch)
    disp_pairs: list[tuple[int, str]] = [(i, cells[i]) for i in range(len(cells)) if cells[i].isdigit()]
    if len(disp_pairs) < len(work_ds):
        raise ValueError("被除数原式补零后数位少于移位工作串")
    col_map = [disp_pairs[-len(work_ds) + j][0] for j in range(len(work_ds))]
    pz: list[int] = []
    i = 0
    while i < len(cells) and cells[i] == "0":
        pz.append(i)
        i += 1
    pdot: list[int] = []
    if i < len(cells) and cells[i] == ".":
        pdot.append(i)
        i += 1
    # 小数点后、首个非 0 前的连续占位 0（如 0.048 中 4 前的 0）与整数前导 0、小数点一并短划
    while i < len(cells) and cells[i] == "0":
        pz.append(i)
        i += 1
    new_dot_idx: int | None = None
    # 仅为对齐 work_ds 在 fp 右侧补的连续 0（不含 fp 原有数位），标红用下标；在插入新小数点之前基于 cells 下标计算
    fp_pad_red: list[int] = []
    if extra > 0:
        base = len(ip) + 1 + len(fp)  # 第一个补 0 在「整数部分 + '.' + fp」之后
        fp_pad_red = [base + t for t in range(extra) if base + t < len(cells) and cells[base + t] == "0"]
    # 移位后被除数仍带小数：在「工作串第 dec_after 位数字」前插入新小数点（如 8192、dec_after=3 → …9.2…）
    if 0 < dec_after < len(work_ds):
        ins = col_map[dec_after]
        cells.insert(ins, ".")
        new_dot_idx = ins
        for j in range(dec_after, len(col_map)):
            col_map[j] += 1
        fp_pad_red = [i + 1 if i >= ins else i for i in fp_pad_red]
    return cells, col_map, pz, pdot, new_dot_idx, fp_pad_red


def _dividend_cells_shifted_digits(ds: str, dec_after: int, extra_trailing_zeros: int) -> list[str]:
    """竖式内被除数行：移位后的数字串 + 小数点（整数被除数不画末尾点）。"""
    body = ds + ("0" * extra_trailing_zeros)
    if dec_after >= len(ds) and extra_trailing_zeros == 0:
        return list(body)
    cells: list[str] = []
    for j, ch in enumerate(body):
        if j == dec_after:
            cells.append(".")
        cells.append(ch)
    return cells


def _dividend_shifted_extension_red_digit_cells(ds: str, dec_after: int, extra_trailing_zeros: int) -> list[int]:
    """与 `_dividend_cells_shifted_digits` 一致布局下，续除补在尾部的 `0` 所在 cell 下标（与新增小数点同色）。"""
    if extra_trailing_zeros <= 0:
        return []
    body = ds + ("0" * extra_trailing_zeros)
    red: list[int] = []
    ci = 0
    for j, ch in enumerate(body):
        if j == dec_after:
            ci += 1
        if ch == "0" and j >= len(ds):
            red.append(ci)
        ci += 1
    return red


def _decimal_frac_digit_count(da: Decimal) -> int:
    """被除数横式中的小数位数（用于与除数右移位数 k 相减，得移位产生的尾零个数）。"""
    exp = da.as_tuple().exponent
    return -exp if exp < 0 else 0


def _divisor_shift_scale_suffix_red_digit_cells(
    da: Decimal, ds: str, k_div: int, dvd_cells: list[str]
) -> list[int]:
    """除数小数点右移 k 位时，被除数同步 ×10^k 在移位数字串 ds 末尾多出的连续 0（如 16÷0.25→1600 的 00）。"""
    if k_div <= 0 or not ds:
        return []
    frac = _decimal_frac_digit_count(da)
    suffix_len = max(0, k_div - frac)
    if suffix_len <= 0:
        return []
    tail_zero_run = 0
    for ch in reversed(ds):
        if ch == "0":
            tail_zero_run += 1
        else:
            break
    take = min(suffix_len, tail_zero_run)
    if take <= 0:
        return []
    digit_pos = [i for i, ch in enumerate(dvd_cells) if ch.isdigit()]
    if len(digit_pos) != len(ds):
        return []
    out: list[int] = []
    for j in range(len(ds) - take, len(ds)):
        if ds[j] == "0":
            out.append(digit_pos[j])
    return out


def _dividend_old_decimal_gap_after_digit_idx(dvd_norm: str) -> int | None:
    """原横式被除数小数点左侧至少有一位数字时，返回「该点」落在移位数字串里哪两个数字之间（左位下标）。"""
    if "." not in dvd_norm:
        return None
    ip, _fp = dvd_norm.split(".", 1)
    pos = len(ip)
    if pos <= 0:
        return None
    return pos - 1


def _digit_col_to_cell_idx(dvd_cells: list[str], dcol: int) -> int:
    di = 0
    for ci, ch in enumerate(dvd_cells):
        if ch == ".":
            continue
        if di == dcol:
            return ci
        di += 1
    raise IndexError("列索引越界")


def _remap_layout_cell_columns(
    dvd_cells: list[str],
    layout: LongDivisionLayout,
    work_digit_col_to_cell: list[int] | None = None,
) -> LongDivisionLayout:
    def _cell_for_digit_col(dcol: int) -> int:
        if work_digit_col_to_cell is not None:
            return work_digit_col_to_cell[dcol]
        return _digit_col_to_cell_idx(dvd_cells, dcol)

    steps2 = [
        DivisionStep(
            partial=s.partial,
            quotient_digit=s.quotient_digit,
            product=s.product,
            partial_start_col=_cell_for_digit_col(s.partial_start_col),
            partial_end_col=_cell_for_digit_col(s.partial_end_col),
            remainder_after=s.remainder_after,
        )
        for s in layout.steps
    ]
    slots2 = [(_cell_for_digit_col(c), d) for c, d in layout.quotient_slots]
    frac2 = [(_cell_for_digit_col(c), d) for c, d in layout.quotient_frac_slots]
    return LongDivisionLayout(
        scaled_dividend=layout.scaled_dividend,
        scaled_divisor=layout.scaled_divisor,
        quotient=layout.quotient,
        quotient_slots=slots2,
        steps=steps2,
        final_remainder=layout.final_remainder,
        quotient_frac_slots=frac2,
        has_quotient_decimal_point=layout.has_quotient_decimal_point,
        dividend_dec_after=layout.dividend_dec_after,
        quotient_recurring_dot_frac_slot_index=layout.quotient_recurring_dot_frac_slot_index,
    )


def horizontal_equation(dividend: str, divisor: str, quotient: str) -> str:
    return f"{_normalize_decimal_str(dividend)} ÷ {_normalize_decimal_str(divisor)} = {quotient}"


def _terminating_denominator_after_reduce(num: int, den: int) -> bool:
    """最简分数 num/den 的小数部分是否有限（分母仅含质因子 2、5）。"""
    d = den // gcd(num, den)
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    return d == 1


def _repeating_transient_and_cycle(rem: int, den: int) -> tuple[str, str]:
    """真分数 rem/den（0<rem<den，且与 den 已约简）的小数展开：非循环段、循环节。"""
    seen: dict[int, int] = {}
    digits: list[str] = []
    pos = 0
    r = rem
    while r != 0:
        if r in seen:
            i = seen[r]
            return "".join(digits[:i]), "".join(digits[i:])
        seen[r] = pos
        r *= 10
        digits.append(str(r // den))
        r = r % den
        pos += 1
    return "".join(digits), ""


def _display_frac_digits_for_repeating(transient: str, cycle: str) -> str:
    """竖式续除用的小数部分数字串（无小数点）；纯循环节长度>1 时取一整节，单数字循环只写一个数字（与 3.\\dot{3} 一致）。"""
    if not cycle:
        return transient
    if transient:
        return transient + cycle
    if len(cycle) == 1:
        return cycle
    return cycle


def _try_build_repeating_quotient_layout(
    base: LongDivisionLayout,
    scaled_dividend: int,
    scaled_divisor: int,
) -> LongDivisionLayout | None:
    """若 scaled_dividend/scaled_divisor 为无限循环小数，则续除若干步并标记循环位；否则返回 None。"""
    if base.final_remainder == 0:
        return None
    g = gcd(scaled_dividend, scaled_divisor)
    num, den = scaled_dividend // g, scaled_divisor // g
    if _terminating_denominator_after_reduce(num, den):
        return None
    rem = num % den
    if rem == 0:
        return None
    transient, cycle = _repeating_transient_and_cycle(rem, den)
    if not cycle:
        return None
    display_frac = _display_frac_digits_for_repeating(transient, cycle)
    ext = apply_fractional_quotient_extension(
        base, scaled_dividend, scaled_divisor, len(display_frac)
    )
    dot_idx = len(display_frac) - 1
    q_disp = f"{base.quotient}.{display_frac}"
    return LongDivisionLayout(
        scaled_dividend=ext.scaled_dividend,
        scaled_divisor=ext.scaled_divisor,
        quotient=q_disp,
        quotient_slots=list(ext.quotient_slots),
        steps=list(ext.steps),
        final_remainder=ext.final_remainder,
        quotient_frac_slots=list(ext.quotient_frac_slots),
        has_quotient_decimal_point=True,
        dividend_dec_after=ext.dividend_dec_after,
        quotient_recurring_dot_frac_slot_index=dot_idx,
    )


def _fmt_verify_decimal(q: Decimal) -> str:
    s = strip_trailing_frac_zeros_from_f_str(format(q, "f"))
    return s if s else "0"


def _factor_decimal_place_count(display: str) -> int:
    """横式因子书写中小数点后的位数（含末尾 0），用于验算竖式补位。"""
    if "." not in display:
        return 0
    return len(display.split(".", 1)[1])


def _verification_product_mul_display(prod_display: str, f_top: str, f_bot: str) -> str:
    """
    验算乘法横式积：按「上、下因子横式小数位数之和」固定小数位数，与内层整数积列对齐，便于再划去小数部分多余 0。

    此前仅处理「积为无小数点整数串」；若已为 `1.5` 等最简小数则早退，导致无法补成 `1.50`（与 25×6=150 的竖式对齐）。
    现统一用 Decimal 量化到 10^-need 位（如 1.5、need=2 → 1.50；100、need=2 → 100.00）。
    """
    need = _factor_decimal_place_count(f_top) + _factor_decimal_place_count(f_bot)
    if need <= 0:
        return prod_display
    need = min(need, 12)
    try:
        d = Decimal(_normalize_decimal_str(prod_display))
    except (ValueError, InvalidOperation):
        return prod_display
    quant = Decimal(10) ** -need
    qd = d.quantize(quant, rounding=ROUND_HALF_UP)
    # 此处不得再 strip 小数尾 0： pedagogical 位宽依赖固定小数位（如 1.50）
    return format(qd, "f")


def _verification_product_append_bot_echo_frac_zeros(
    prod_display: str,
    factor_bot_display: str,
    int_layout: SchoolMultiplyLayout,
    strip_trailing_int: int,
) -> str:
    """
    乘数横式为「内层有效数字 + 右侧不参与运算的 0」（如 800→8、30→3）时，
    在真积小数部分末尾补 0，便于红斜线划去（与乘数尾零一一对应）。
    若量化后小数部分已有末尾 0（如 0.480），只补「strip 尾零个数 − 已有末尾 0 个数」，避免多补成 0.4800。
    若尾零写在上一行（如 250→25）则不在此补（由 _verification_product_mul_display 等处理）。
    """
    if strip_trailing_int <= 0 or "." not in prod_display:
        return prod_display
    sig = _digit_row_sig(int_layout.bot)
    db = "".join(ch for ch in factor_bot_display if ch.isdigit())
    if len(db) < len(sig) + strip_trailing_int:
        return prod_display
    if db[:-strip_trailing_int] != sig:
        return prod_display
    if any(ch != "0" for ch in db[-strip_trailing_int:]):
        return prod_display
    ip, fp = prod_display.split(".", 1)
    # _verification_product_mul_display 已按因子小数位数量子化，小数部分末尾可能已有尾 0
    #（如 0.016×30 → 0.480）。此处只补「尚缺」的个数，避免 0.480 再补成 0.4800 而多出一个不参与划线的 0。
    z_in_fp = 0
    for ch in reversed(fp):
        if ch == "0":
            z_in_fp += 1
        else:
            break
    n_extra = max(0, strip_trailing_int - z_in_fp)
    if n_extra == 0:
        return prod_display
    return f"{ip}.{fp}{'0' * n_extra}"


def _verification_scaled_pair(
    q: Decimal, d: Decimal, max_exp: int = 14
) -> tuple[str, str, int, int] | None:
    """返回 (ta, tb, pq, pr)；数位过长则 None。"""
    pq = min(max(0, -int(q.as_tuple().exponent)), max_exp)
    pr = min(max(0, -int(d.as_tuple().exponent)), max_exp)
    ta = int(q * (Decimal(10) ** pq))
    tb = int(d * (Decimal(10) ** pr))
    if len(str(ta)) > 18 or len(str(tb)) > 18:
        return None
    return str(ta), str(tb), pq, pr


def _verification_int_factors(q: Decimal, d: Decimal, max_exp: int = 14) -> tuple[str, str] | None:
    """将商、除数缩成整数相乘以画竖式；数位过长则放弃部分积进位竖式。"""
    r = _verification_scaled_pair(q, d, max_exp)
    if r is None:
        return None
    return r[0], r[1]


def _strip_trailing_zero_run_int_str(s: str) -> tuple[str, int]:
    """非负整数字符串去掉右侧连续 0，返回 (去尾后, 去掉的个数)。"""
    if not s.isdigit():
        return s, 0
    t = s.rstrip("0")
    k = len(s) - len(t)
    if not t:
        return "0", k
    return t, k


def _digit_row_sig(row: DigitRow) -> str:
    return "".join(ch for _, ch in sorted(row.cells.items()))


def _verify_factor_digit_run_len(display: str) -> int:
    """横式因子中数字字符个数（含整数部分前导 0，如 0.25→3）。"""
    return sum(1 for c in display if c.isdigit())


def _factor_operative_digit_count(display: str) -> int:
    """竖式换位用：参与乘法的「有效数字」个数（与内层整数乘对齐思路一致）。

    - 纯整数：去掉左侧前导 0 后，再去掉右侧整十整百尾 0（如 30→1、250→2），全 0 为 1。
    - 含小数点：从全体数字位中首个非 0 起到末位（略去整数前导 0 及小数点后首非 0 前的 0），
      如 0.032→2（32），25.6→3（256）。
    """
    s = _normalize_decimal_str(display)
    if "." not in s:
        t = s.lstrip("0") or "0"
        t = t.rstrip("0") or "0"
        return max(1, len(t))
    ip, fp = s.split(".", 1)
    digits: list[str] = []
    for c in ip:
        if c.isdigit():
            digits.append(c)
    for c in fp:
        if c.isdigit():
            digits.append(c)
    i = 0
    while i < len(digits) and digits[i] == "0":
        i += 1
    if i >= len(digits):
        return 1
    return len(digits) - i


def _swap_verify_factors_digit_rich_on_top(
    f_top: str,
    f_bot: str,
    ta: str,
    tb: str,
) -> tuple[str, str, str, str]:
    """若下行「运算有效数字」个数多于上行，则交换上下因子及内层 ta/tb（乘积不变）。"""
    if _factor_operative_digit_count(f_bot) > _factor_operative_digit_count(f_top):
        return f_bot, f_top, tb, ta
    return f_top, f_bot, ta, tb


def _try_strip_verify_multiply(
    q: Decimal,
    d: Decimal,
    d_norm: str,
    q_disp: str,
    scaled: tuple[str, str, int, int],
) -> tuple[str, str, SchoolMultiplyLayout, int] | None:
    """
    验算乘法列与横式对齐：当「横式上的商 / 除数」与「去掉商（或乘数）右侧若干 0 后的整数因子」
    在数值上仍与缩放整数乘积一致时，用该整数乘法竖式排进位列，横式仍画完整商与除数（含尾零、小数点）。

    仅用于验算列与整数乘法一致；竖式里是否省略某条过渡行由 svg_render 按「删多余步骤」决定，
    与是否匹配本函数无必然一一对应。

    适用：pq==0, pr>0 且 (ta×tb)//10**trail == int(tb)×int(mulc)；或 pq>0, pr==0 且去尾后乘数为一位数等（见实现）。
    返回 (上因子横式, 下因子横式, 内层 SchoolMultiplyLayout, 商侧剥离的尾零个数)；不适用则 None。

    横式上下顺序（pq==0 且 pr>0 时）：若除数横式「运算有效数字」个数大于商横式，则除数在上、商在下，
    内层 layout_integer_multiply(multicore, mulc)，否则商上、除数下（与 _factor_operative_digit_count 一致）。
    """
    ta, tb, pq, pr = scaled
    ta_i, tb_i = int(ta), int(tb)
    if not ((pq == 0 and pr > 0) or (pq > 0 and pr == 0)):
        return None
    if pq == 0 and pr > 0:
        mulc, trail = _strip_trailing_zero_run_int_str(ta)
        multicore = str(tb)
        if trail < 1 or not mulc or mulc == "0":
            return None
        core_prod = (ta_i * tb_i) // (10**trail)
        if int(multicore) * int(mulc) != core_prod:
            return None
        # 横式上下顺序：按横式上「运算有效数字」多的在上（与 _swap_verify_factors_digit_rich_on_top 一致）
        top, bot = q_disp, d_norm
        inner = layout_integer_multiply(mulc, multicore)
        if _factor_operative_digit_count(d_norm) > _factor_operative_digit_count(q_disp):
            top, bot = d_norm, q_disp
            inner = layout_integer_multiply(multicore, mulc)
    else:
        mulc, trail = _strip_trailing_zero_run_int_str(tb)
        multicore = str(ta)
        if trail < 1 or len(mulc) != 1 or mulc == "0":
            return None
        core_prod = (ta_i * tb_i) // (10**trail)
        if int(multicore) * int(mulc) != core_prod:
            return None
        # 内层已是「较长整数 × 一位数」；横式仍上商下除数（该情形下行有效位恒为 1，无需再交换）
        top, bot = q_disp, d_norm
        inner = layout_integer_multiply(multicore, mulc)
    return top, bot, inner, trail


def _verification_decimal_shift(q: Decimal, d: Decimal, max_exp: int = 14) -> int:
    """与 _verification_int_factors 相同的小数位截取规则；整数积 ÷ 10^返回值 = 真积。"""
    pq = min(max(0, -int(q.as_tuple().exponent)), max_exp)
    pr = min(max(0, -int(d.as_tuple().exponent)), max_exp)
    return pq + pr


def _horizontal_quotient_with_recurring_dot(quotient: str, recurring_frac_slot_index: int | None) -> str:
    """在商字符串小数部分第 recurring_frac_slot_index 个数字后加 U+0307（组合用 dot above）。"""
    if recurring_frac_slot_index is None or "." not in quotient:
        return quotient
    _ip, fp = quotient.split(".", 1)
    if not fp or recurring_frac_slot_index < 0 or recurring_frac_slot_index >= len(fp):
        return quotient
    k = len(_ip) + 1 + recurring_frac_slot_index
    return quotient[: k + 1] + "\u0307" + quotient[k + 1 :]


def _build_multiplication_division_verify_svg(
    prod_s: str,
    factor_a_display: str,
    factor_b_display: str,
    *,
    style: Style,
) -> str:
    """积 ÷ 因数 = 另一因数；优先用第二个因数作除数（与横式 a×b 顺序一致），失败时再对调（规避个别商前导零与竖式槽位不一致）。"""
    div_first = _normalize_decimal_str(factor_b_display)
    div_second = _normalize_decimal_str(factor_a_display)
    if div_first == "0" or div_second == "0":
        raise ValueError("除数为 0 时无法用除法验算乘法")
    last_slot_mismatch: ValueError | None = None
    for div_s in (div_first, div_second):
        try:
            return build_combined_svg(
                prod_s,
                div_s,
                include_verification=False,
                retain_decimal_places=None,
                style=style,
            )
        except ValueError as e:
            if "竖式商位与精确商数字个数不一致" not in str(e):
                raise
            last_slot_mismatch = e
    assert last_slot_mismatch is not None
    raise last_slot_mismatch


def _extend_to_exact_finite_quotient(
    base: LongDivisionLayout, dividend: int, divisor: int
) -> LongDivisionLayout:
    """竖式有余数时，自动补 0 续除直至除尽（仅适用于商为有限小数的情形）。"""
    for max_f in range(1, 31):
        cand = apply_fractional_quotient_extension(base, dividend, divisor, max_f)
        if cand.final_remainder == 0:
            return cand
    raise ValueError(
        "移位后的整数除法不能除尽为有限小数；请调整输入或传入 retain_decimal_places 指定保留位数"
    )


def build_combined_svg(
    dividend: str,
    divisor: str,
    *,
    include_verification: bool = False,
    retain_decimal_places: int | None = None,
    style: Style | None = None,
) -> str:
    """生成除法竖式 SVG 的**唯一入口**（MCP `render_division_vertical` 仅调用本函数）。

    所有算式共用同一套逻辑，不针对某一题特判：
    - `scaled_dividend_digits_for_divisor_shift`：按除数小数位数同步移位被除数；
    - `long_division_layout_embedded`：教材式分步竖式（含商的小数分列）；
    - `compute_shift_marks` + `render_division_svg`：除数前导零/小数点划去、被除数原小数点
      （两数字正中红点 + 短划）与移位后新小数点（红）、商的小数点与列对齐。
    未传 `retain_decimal_places` 且商为无限循环小数时：按最简分母判定，续除「非循环+一节循环」位，
    横式在循环末位后加 U+0307，竖式商该小数位上方画红点；仍为有限小数时则续除至除尽。
    `retain_decimal_places` / `include_verification` 仍按原语义（四舍五入位数、验算块）。
    """
    D, _B, k_max, div_orig, dvd_orig = decimal_to_scaled_ints(dividend, divisor)
    da = Decimal(_normalize_decimal_str(dvd_orig))
    db = Decimal(_normalize_decimal_str(div_orig))
    ds, dec_after, k_div, B_int = scaled_dividend_digits_for_divisor_shift(da, db)
    gap_after = _dividend_old_decimal_gap_after_digit_idx(dvd_orig)

    layout0 = long_division_layout_embedded(ds, dec_after, B_int)
    if retain_decimal_places is not None:
        if retain_decimal_places < 0:
            raise ValueError("retain_decimal_places 须 >= 0")
        layout0 = apply_fractional_quotient_extension(
            layout0, D, B_int, retain_decimal_places + 1
        )
    elif layout0.final_remainder != 0:
        rep = _try_build_repeating_quotient_layout(layout0, D, B_int)
        if rep is not None:
            layout0 = rep
        else:
            layout0 = _extend_to_exact_finite_quotient(layout0, int(layout0.scaled_dividend), B_int)

    extra = len(layout0.scaled_dividend) - len(ds)
    dvd_norm = _normalize_decimal_str(dvd_orig)
    work_map: list[int] | None = None
    pz_strike: list[int] = []
    pd_strike: list[int] = []
    extension_red_cells: list[int] = []
    if _should_use_pedagogical_zero_shift_dividend_row(dvd_norm, ds, k_div):
        dvd_cells, work_map, pz_strike, pd_strike, new_dot_idx, fp_pad_red = (
            _build_pedagogical_zero_shift_dividend(dvd_norm, ds, dec_after)
        )
        gap_after = None
        extension_red_cells = list(fp_pad_red)
        # 续除 / 循环节等使 scaled_dividend 长于初始 ds：右侧补 0 并扩展「数位列 → 格子」映射（与移位串路径的 extra 一致）
        for _ in range(extra):
            dvd_cells.append("0")
            work_map.append(len(dvd_cells) - 1)
        if extra:
            extension_red_cells.extend(
                i
                for i in range(len(dvd_cells) - extra, len(dvd_cells))
                if dvd_cells[i] == "0"
            )
        extension_red_cells = sorted(set(extension_red_cells))
    else:
        dvd_cells = _dividend_cells_shifted_digits(ds, dec_after, extra)
        new_dot_idx = dvd_cells.index(".") if "." in dvd_cells else None
        extension_red_cells = _dividend_shifted_extension_red_digit_cells(ds, dec_after, extra)
        scale_red = _divisor_shift_scale_suffix_red_digit_cells(da, ds, k_div, dvd_cells)
        extension_red_cells = sorted(set(extension_red_cells) | set(scale_red))
    marks = compute_shift_marks(
        div_orig,
        dvd_orig,
        k_div,
        dividend_old_decimal_gap_after_digit=gap_after,
        dividend_new_decimal_cell_index=new_dot_idx,
        dividend_prefix_zero_strike_cells=pz_strike or None,
        dividend_prefix_dot_strike_cells=pd_strike or None,
        dividend_extension_red_digit_cells=extension_red_cells or None,
    )
    layout = _remap_layout_cell_columns(dvd_cells, layout0, work_map)
    div_cells = list(_normalize_decimal_str(div_orig))

    div_svg = render_division_svg(
        divisor_cells=div_cells,
        dividend_cells=dvd_cells,
        marks=marks,
        layout=layout,
        st=style,
    )

    if not include_verification:
        return div_svg

    if getattr(layout, "quotient_recurring_dot_frac_slot_index", None) is not None:
        q_dec = da / db
    else:
        q_dec = Decimal(layout.quotient)
    d_dec = Decimal(_normalize_decimal_str(div_orig))
    prod = q_dec * d_dec
    prod_plain = strip_trailing_frac_zeros_from_f_str(format(prod, "f"))
    # 验算横式积与 q×d 数值一致；竖式上再按因子小数位数补「.0…」以便划去多余 0（见 _verification_product_mul_display）
    prod_display = prod_plain if prod_plain else "0"

    st0 = style or Style()
    scaled = _verification_scaled_pair(q_dec, d_dec)
    strip: tuple[str, str, SchoolMultiplyLayout, int] | None = None
    if scaled is not None:
        strip = _try_strip_verify_multiply(
            q_dec,
            d_dec,
            _normalize_decimal_str(div_orig),
            _fmt_verify_decimal(q_dec),
            scaled,
        )
    if strip is not None:
        f_top, f_bot, int_layout, strip_trail = strip
        strip_trailing_int = strip_trail
    else:
        f_top = _fmt_verify_decimal(q_dec)
        f_bot = _normalize_decimal_str(div_orig)
        strip_trailing_int = 0
        if scaled is None:
            int_layout = None
        else:
            ta0, tb0 = scaled[0], scaled[1]
            f_top, f_bot, ta0, tb0 = _swap_verify_factors_digit_rich_on_top(f_top, f_bot, ta0, tb0)
            int_layout = layout_integer_multiply(ta0, tb0)
    prod_display = _verification_product_mul_display(prod_display, f_top, f_bot)
    if strip is not None:
        prod_display = _verification_product_append_bot_echo_frac_zeros(
            prod_display, f_bot, int_layout, strip_trailing_int
        )
    # strip 且 pq==0：内层为 (ta/10^trail)×tb，真积 = 内层积 / 10^(pr−trail)，故列对齐用 pr−trail，勿用 pq+pr
    prod_shift = None
    if scaled is not None:
        ta_s, tb_s, pq_s, pr_s = scaled
        if strip is not None and pq_s == 0 and pr_s > 0:
            prod_shift = pr_s - strip_trailing_int
        else:
            prod_shift = pq_s + pr_s
    mul_svg, mw, mh, _, mul_ink = render_verification_multiplication_svg(
        factor_top_display=f_top,
        factor_bot_display=f_bot,
        product_display=prod_display,
        int_layout=int_layout,
        product_decimal_shift=prod_shift,
        verification_strip_trailing_int=strip_trailing_int,
        st=st0,
    )

    m = re.search(r'height="([0-9.]+)"', div_svg)
    h1 = float(m.group(1)) if m else 200
    div_w = float(re.search(r'width="([0-9.]+)"', div_svg).group(1))
    div_ink = division_subtraction_ink_right_x(div_cells, dvd_cells, st0)
    if mul_ink > div_ink:
        div_ox = mul_ink - div_ink
        mul_ox = 0.0
    else:
        div_ox = 0.0
        mul_ox = div_ink - mul_ink
    # 主竖式底 →「验算：」所在行顶：20px；「验算：」与下方乘法竖式之间另留小间距
    gap_div_to_verify_label = 20.0
    label_gap_to_mul = 8.0
    label_fs = (st0.font_size + 2.0) * 0.75
    label_line_h = label_fs * 1.22
    total_w = max(div_ox + div_w, mul_ox + mw)
    label_y = h1 + gap_div_to_verify_label
    label_text_y = label_y + label_fs * 0.35
    mul_ty = label_y + label_line_h + label_gap_to_mul
    total_h = mul_ty + mh

    inner_div = re.sub(r"<svg[^>]*>", "", div_svg, count=1)
    inner_div = inner_div.rsplit("</svg>", 1)[0]
    inner_mul = re.sub(r"<svg[^>]*>", "", mul_svg, count=1)
    inner_mul = re.sub(
        r'<rect width="100%" height="100%" fill="white"/>',
        "",
        inner_mul,
        count=1,
    )
    inner_mul = inner_mul.rsplit("</svg>", 1)[0]

    ff = st0.font_family.replace("&", "&amp;").replace('"', "&quot;")
    label_t = (
        f'<text x="20.00" y="{label_text_y:.2f}" text-anchor="start" '
        f'font-family="{ff}" font-size="{label_fs:.1f}" fill="{st0.color_main}" '
        f'dominant-baseline="middle">验算：</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.1f}" height="{total_h:.1f}" '
        f'viewBox="0 0 {total_w:.1f} {total_h:.1f}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        f'<g transform="translate({div_ox:.2f},0)">{inner_div}</g>'
        f"{label_t}"
        f'<g transform="translate({mul_ox:.2f},{mul_ty:.2f})">{inner_mul}</g>'
        f"</svg>"
    )


def _svg_parse_wh(svg: str) -> tuple[float, float]:
    m = re.search(r'width="([0-9.]+)"', svg)
    m2 = re.search(r'height="([0-9.]+)"', svg)
    if not m or not m2:
        return 400.0, 300.0
    return float(m.group(1)), float(m2.group(1))


def _svg_strip_outer(svg: str) -> str:
    inner = re.sub(r"<svg[^>]*>", "", svg, count=1)
    inner = re.sub(r'<rect width="100%" height="100%" fill="white"/>', "", inner, count=1)
    return inner.rsplit("</svg>", 1)[0]


def _stack_main_and_verification_svgs(
    main_svg: str,
    verify_svgs: list[str],
    style: Style,
    *,
    mul_slack_mask: list[bool] | None = None,
    main_ink_right: float | None = None,
    verify_ink_rights: list[float] | None = None,
) -> str:
    """主图在上；若有验算则在下方空行左起「验算：」，再垂直堆叠若干验算块。

    主图与各验算块的 **右缘** 与画布右缘对齐；不改变各子 SVG 内部坐标。

    若同时传入 `main_ink_right` 与等长的 `verify_ink_rights`，则按**墨迹右缘**（与
    `build_combined_svg` 中除法+乘法验算一致）对齐，而非按子图 `width` 外框对齐。
    `mul_slack_mask` 保留为兼容旧调用，已不再影响水平位置。
    """
    _ = mul_slack_mask
    st0 = style or Style()
    if not verify_svgs:
        return main_svg
    w0, h0 = _svg_parse_wh(main_svg)
    verify_dims = [_svg_parse_wh(vs) for vs in verify_svgs]
    w0f = float(w0)
    if (
        main_ink_right is not None
        and verify_ink_rights is not None
        and len(verify_ink_rights) == len(verify_svgs)
    ):
        d_ink = float(main_ink_right)
        m_list = [float(x) for x in verify_ink_rights]
        r_align = max(d_ink, *m_list)
        main_ox = r_align - d_ink
        oxs = [r_align - m_list[i] for i in range(len(verify_dims))]
        total_w = max(
            main_ox + w0f,
            *(oxs[i] + float(verify_dims[i][0]) for i in range(len(verify_dims))),
        )
    else:
        total_w = max(w0f, *(float(vw) for vw, _vh in verify_dims))
        main_ox = total_w - w0f
        oxs = [total_w - float(verify_dims[i][0]) for i in range(len(verify_dims))]
    inner_main = _svg_strip_outer(main_svg)
    gap_label = 20.0
    label_gap_to_block = 8.0
    between_blocks = 14.0
    label_fs = (st0.font_size + 2.0) * 0.75
    label_line_h = label_fs * 1.22
    bottom_pad = 12.0
    ff = st0.font_family.replace("&", "&amp;").replace('"', "&quot;")

    y_label = h0 + gap_label
    label_text_y = y_label + label_fs * 0.35
    y_block = y_label + label_line_h + label_gap_to_block
    label_t = (
        f'<text x="20.00" y="{label_text_y:.2f}" text-anchor="start" '
        f'font-family="{ff}" font-size="{label_fs:.1f}" fill="{st0.color_main}" '
        f'dominant-baseline="middle">验算：</text>'
    )
    g_main = f'<g transform="translate({main_ox:.2f},0)">{inner_main}</g>'
    verify_gs: list[str] = []
    for i, vs in enumerate(verify_svgs):
        vw, vh = verify_dims[i]
        ox = oxs[i]
        inner = _svg_strip_outer(vs)
        verify_gs.append(f'<g transform="translate({ox:.2f},{y_block:.2f})">{inner}</g>')
        y_block += vh + (between_blocks if i < len(verify_svgs) - 1 else 0.0)
    total_h = y_block + bottom_pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.1f}" height="{total_h:.1f}" '
        f'viewBox="0 0 {total_w:.1f} {total_h:.1f}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        f"{g_main}"
        f"{label_t}"
        f'{"".join(verify_gs)}'
        f"</svg>"
    )


def _prepare_verification_multiplication_svg(
    q_dec: Decimal,
    d_dec: Decimal,
    *,
    d_norm: str,
    q_disp: str,
    style: Style | None = None,
) -> tuple[str, float, float, int | None, float]:
    """与除法验算相同的乘法竖式管线（横式因子 + 内层整数乘 + 积划尾零等）。

    返回 (svg, w, h, digit_grid_columns, ink_right)，与 `render_verification_multiplication_svg` 一致。
    """
    prod = q_dec * d_dec
    prod_plain = strip_trailing_frac_zeros_from_f_str(format(prod, "f"))
    prod_display = prod_plain if prod_plain else "0"
    st0 = style or Style()
    scaled = _verification_scaled_pair(q_dec, d_dec)
    strip: tuple[str, str, SchoolMultiplyLayout, int] | None = None
    if scaled is not None:
        strip = _try_strip_verify_multiply(q_dec, d_dec, d_norm, q_disp, scaled)
    if strip is not None:
        f_top, f_bot, int_layout, strip_trail = strip
        strip_trailing_int = strip_trail
    else:
        f_top = q_disp
        f_bot = d_norm
        strip_trailing_int = 0
        if scaled is None:
            int_layout = None
        else:
            ta0, tb0 = scaled[0], scaled[1]
            f_top, f_bot, ta0, tb0 = _swap_verify_factors_digit_rich_on_top(f_top, f_bot, ta0, tb0)
            int_layout = layout_integer_multiply(ta0, tb0)
    prod_display = _verification_product_mul_display(prod_display, f_top, f_bot)
    if strip is not None:
        prod_display = _verification_product_append_bot_echo_frac_zeros(
            prod_display, f_bot, int_layout, strip_trailing_int
        )
    prod_shift = None
    if scaled is not None:
        _ta, _tb, pq_s, pr_s = scaled
        if strip is not None and pq_s == 0 and pr_s > 0:
            prod_shift = pr_s - strip_trailing_int
        else:
            prod_shift = pq_s + pr_s
    return render_verification_multiplication_svg(
        factor_top_display=f_top,
        factor_bot_display=f_bot,
        product_display=prod_display,
        int_layout=int_layout,
        product_decimal_shift=prod_shift,
        verification_strip_trailing_int=strip_trailing_int,
        st=st0,
    )


def build_addition_vertical_svg(
    addend_a: str,
    addend_b: str,
    *,
    include_verification: bool = False,
    style: Style | None = None,
) -> str:
    la = layout_integer_addition(addend_a, addend_b)
    main = render_addition_vertical_svg(la, st=style)
    if not include_verification:
        return main
    bn = normalize_nonneg_integer_operand(addend_b)
    an = normalize_nonneg_integer_operand(addend_a)
    sum_s = str(int(an) + int(bn))
    lv = layout_integer_subtraction(sum_s, bn)
    v = render_subtraction_vertical_svg(lv, st=style)
    return _stack_main_and_verification_svgs(main, [v], style or Style(), mul_slack_mask=None)


def build_subtraction_vertical_svg(
    minuend: str,
    subtrahend: str,
    *,
    include_verification: bool = False,
    style: Style | None = None,
) -> str:
    ls = layout_integer_subtraction(minuend, subtrahend)
    main = render_subtraction_vertical_svg(ls, st=style)
    if not include_verification:
        return main
    bn = normalize_nonneg_integer_operand(subtrahend)
    diff_s = _digit_row_sig(ls.diff_row)
    la = layout_integer_addition(diff_s, bn)
    v = render_addition_vertical_svg(la, st=style)
    return _stack_main_and_verification_svgs(main, [v], style or Style(), mul_slack_mask=None)


def build_multiplication_vertical_svg(
    factor_a: str,
    factor_b: str,
    *,
    include_verification: bool = False,
    style: Style | None = None,
) -> str:
    da = Decimal(_normalize_decimal_str(factor_a))
    db = Decimal(_normalize_decimal_str(factor_b))
    st0 = style or Style()
    svg_m, mw, mh, _, _ = _prepare_verification_multiplication_svg(
        da,
        db,
        d_norm=_normalize_decimal_str(factor_b),
        q_disp=_fmt_verify_decimal(da),
        style=st0,
    )
    if not include_verification:
        return svg_m
    if db == 0:
        raise ValueError("除数为 0 时无法用除法验算乘法")
    prod_plain = strip_trailing_frac_zeros_from_f_str(format(da * db, "f"))
    prod_s = _normalize_decimal_str(prod_plain if prod_plain else "0")
    verify_svg = _build_multiplication_division_verify_svg(
        prod_s, factor_a, factor_b, style=st0
    )
    return _stack_main_and_verification_svgs(
        svg_m,
        [verify_svg],
        st0,
        mul_slack_mask=[True],
    )


def build_integer_division_vertical_svg(
    dividend: str,
    divisor: str,
    *,
    include_verification: bool = False,
    style: Style | None = None,
) -> str:
    Ds = normalize_nonneg_integer_operand(dividend)
    ds = normalize_nonneg_integer_operand(divisor)
    if ds == "0":
        raise ValueError("除数不能为 0")
    d_int = int(ds)
    D_int = int(Ds)
    layout0 = long_division_layout_embedded(Ds, len(Ds), d_int)
    layout = _remap_layout_cell_columns(list(Ds), layout0, None)
    marks = ShiftMarks(0, 0, False, False, None, None, [], [], [])
    main = render_division_svg(
        divisor_cells=list(ds),
        dividend_cells=list(Ds),
        marks=marks,
        layout=layout,
        st=style,
    )
    if not include_verification:
        return main
    q = int(layout.quotient)
    r = int(layout.final_remainder)
    st0 = style or Style()
    q_dec = Decimal(q)
    d_dec = Decimal(d_int)
    mul_svg, _mw, _mh, mul_grid, mul_ink = _prepare_verification_multiplication_svg(
        q_dec,
        d_dec,
        d_norm=ds,
        q_disp=str(q),
        style=st0,
    )
    div_ink = division_subtraction_ink_right_x(list(ds), list(Ds), st0)
    if r == 0:
        return _stack_main_and_verification_svgs(
            main,
            [mul_svg],
            st0,
            mul_slack_mask=[True],
            main_ink_right=div_ink,
            verify_ink_rights=[mul_ink],
        )
    prod = q * d_int
    prod_s = str(prod)
    r_s = str(r)
    la = layout_integer_addition(prod_s, r_s, grid_width=mul_grid)
    if int(prod_s) + int(r_s) != D_int:
        raise ValueError("内部错误：商×除数+余数与被除数不一致")
    add_svg = render_addition_vertical_svg(la, st=st0)
    add_ink = addition_layout_ink_right_x(la, st0)
    return _stack_main_and_verification_svgs(
        main,
        [mul_svg, add_svg],
        st0,
        mul_slack_mask=[True, False],
        main_ink_right=div_ink,
        verify_ink_rights=[mul_ink, add_ink],
    )
