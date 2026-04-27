"""验算横式积、小数 f 串规范化、整数乘法、组合竖式生成等不变量。

在项目根目录执行::

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest
from decimal import Decimal

from division_vertical_mcp.compose import (
    _build_pedagogical_zero_shift_dividend,
    _dividend_cells_shifted_digits,
    _dividend_shifted_extension_red_digit_cells,
    _divisor_shift_scale_suffix_red_digit_cells,
    _factor_operative_digit_count,
    _fmt_verify_decimal,
    _should_use_pedagogical_zero_shift_dividend_row,
    _verification_product_mul_display,
    build_addition_vertical_svg,
    build_combined_svg,
    build_integer_division_vertical_svg,
    build_multiplication_vertical_svg,
    build_subtraction_vertical_svg,
    horizontal_equation,
)
from division_vertical_mcp.decimal_math import (
    _normalize_decimal_str,
    scaled_dividend_digits_for_divisor_shift,
    strip_trailing_frac_zeros_from_f_str,
)
from division_vertical_mcp.school_multiply import layout_integer_multiply
from division_vertical_mcp import render_config
from division_vertical_mcp.svg_render import (
    _mul_frac_shift_pad_zero_count,
    _mul_should_strike_dot_after_frac_trailing_zeros,
)


class TestMulFracShiftPadZeroCount(unittest.TestCase):
    def test_matrix(self) -> None:
        for fp, exp in [
            ("048", 1),
            ("480", 0),
            ("00", 0),
            ("0", 1),
            ("0012", 2),
        ]:
            with self.subTest(fp=fp):
                self.assertEqual(_mul_frac_shift_pad_zero_count(fp), exp)


class TestMulStrikeMeaninglessDotPredicate(unittest.TestCase):
    def test_matrix(self) -> None:
        for prod, want in [
            (("256.00", 3, [4, 5]), True),
            (("256.0", 3, [4]), True),
            (("10.50", 2, [4]), False),
            (("0.0", 1, [2]), True),
        ]:
            (s, dot_i, strike_j) = prod
            with self.subTest(s=s):
                self.assertEqual(
                    _mul_should_strike_dot_after_frac_trailing_zeros(s, dot_i, strike_j),
                    want,
                )


class TestStripTrailingFracZerosFromFStr(unittest.TestCase):
    def test_integer_strings_unchanged(self) -> None:
        for s in ("100", "0", "20", "1000", "15"):
            with self.subTest(s=s):
                self.assertEqual(strip_trailing_frac_zeros_from_f_str(s), s)

    def test_strips_only_after_dot(self) -> None:
        pairs = [
            ("100.0", "100"),
            ("1.50", "1.5"),
            ("6.00", "6"),
            ("12.3400", "12.34"),
            ("0.0", "0"),
        ]
        for raw, exp in pairs:
            with self.subTest(raw=raw):
                self.assertEqual(strip_trailing_frac_zeros_from_f_str(raw), exp)


class TestVerificationProductMulDisplay(unittest.TestCase):
    def _cases(self) -> list[tuple[str, str, str, str]]:
        return [
            ("100", "25", "4", "100"),
            ("10", "2.5", "4", "10.0"),
            ("1.5", "6", "0.25", "1.50"),
            ("150", "6", "0.25", "150.00"),
            ("0", "0", "0.25", "0.00"),
            ("99", "99", "1", "99"),
            # 横式 2.5 小数段长度为 1，need=2+1=3，21.875 已满足三位小数
            ("21.875", "8.75", "2.5", "21.875"),
            ("0.48", "0.48", "0.016", "0.48000"),
        ]

    def test_matrix(self) -> None:
        for prod, top, bot, exp in self._cases():
            with self.subTest(prod=prod, top=top, bot=bot):
                got = _verification_product_mul_display(prod, top, bot)
                self.assertEqual(
                    got,
                    exp,
                    msg=f"_verification_product_mul_display({prod!r}, {top!r}, {bot!r})",
                )

    def test_invalid_numeric_returns_unchanged(self) -> None:
        got = _verification_product_mul_display("not-a-number", "1", "0.5")
        self.assertEqual(got, "not-a-number")


class TestFactorOperativeDigitCount(unittest.TestCase):
    def test_matrix(self) -> None:
        for s, exp in [
            ("0.032", 2),
            ("25.6", 3),
            ("30", 1),
            ("250", 2),
            ("0.016", 2),
            ("0", 1),
            ("15", 2),
        ]:
            with self.subTest(s=s):
                self.assertEqual(_factor_operative_digit_count(s), exp)


class TestFmtVerifyDecimal(unittest.TestCase):
    def test_matrix(self) -> None:
        for q, exp in [
            (Decimal("6"), "6"),
            (Decimal("1.50"), "1.5"),
            (Decimal("100"), "100"),
            (Decimal("0.25"), "0.25"),
        ]:
            with self.subTest(q=q):
                self.assertEqual(_fmt_verify_decimal(q), exp)


class TestPedagogicalZeroShiftPredicate(unittest.TestCase):
    def test_0p8192_uses_original_row(self) -> None:
        dvd = _normalize_decimal_str("0.8192")
        self.assertTrue(_should_use_pedagogical_zero_shift_dividend_row(dvd, "8192", 3))

    def test_12p6_not_pedagogical(self) -> None:
        dvd = _normalize_decimal_str("12.6")
        self.assertFalse(_should_use_pedagogical_zero_shift_dividend_row(dvd, "1260", 2))

    def test_no_shift_k_zero(self) -> None:
        dvd = _normalize_decimal_str("0.8192")
        self.assertFalse(_should_use_pedagogical_zero_shift_dividend_row(dvd, "8192", 0))


class TestBuildPedagogicalDividendCells(unittest.TestCase):
    def test_0p8192_inserts_shifted_decimal(self) -> None:
        dvd = _normalize_decimal_str("0.8192")
        cells, col_map, _pz, _pd, new_dot, fp_pad_red = _build_pedagogical_zero_shift_dividend(
            dvd, "8192", 3
        )
        self.assertEqual("".join(cells), "0.819.2")
        self.assertEqual(new_dot, 5)
        self.assertEqual(len(col_map), 4)
        self.assertEqual(col_map[-1], 6)
        self.assertEqual(fp_pad_red, [])

    def test_0p1_fp_pad_red_aligns_work_ds(self) -> None:
        dvd = _normalize_decimal_str("0.1")
        cells, _cm, _pz, _pd, _nd, fp_pad_red = _build_pedagogical_zero_shift_dividend(dvd, "10", 2)
        self.assertEqual("".join(cells), "0.10")
        self.assertEqual(fp_pad_red, [3])


class TestScaledDividendDigits(unittest.TestCase):
    def test_0p8192_over_0p032(self) -> None:
        ds, dec_after, k, b = scaled_dividend_digits_for_divisor_shift(
            Decimal("0.8192"), Decimal("0.032")
        )
        self.assertEqual(ds, "8192")
        self.assertEqual(dec_after, 3)
        self.assertEqual(k, 3)
        self.assertEqual(b, 32)


class TestLayoutIntegerMultiplyProduct(unittest.TestCase):
    def _sig(self, ta: str, tb: str) -> str:
        L = layout_integer_multiply(ta, tb)
        return "".join(ch for _, ch in sorted(L.sum_row.cells.items()))

    def test_matrix(self) -> None:
        for ta, tb, prod in [
            ("25", "4", "100"),
            ("12", "34", "408"),
            ("99", "0", "0"),
            ("1", "1", "1"),
            ("0", "7", "0"),
        ]:
            with self.subTest(ta=ta, tb=tb):
                self.assertEqual(self._sig(ta, tb), prod)


class TestHorizontalEquation(unittest.TestCase):
    def test_basic(self) -> None:
        s = horizontal_equation("6", "2", "3")
        self.assertIn("6", s)
        self.assertIn("2", s)
        self.assertIn("3", s)


class TestBuildCombinedNoVerifySmoke(unittest.TestCase):
    """除法竖式（无验算）多组输入不抛错且为合法 SVG。"""

    def test_matrix(self) -> None:
        pairs = [
            ("144", "12"),
            ("10", "3"),
            ("1.5", "0.25"),
            ("0.8192", "0.032"),
            ("25.6", "0.032"),
            ("100", "0.4"),
        ]
        for dvd, div in pairs:
            with self.subTest(dvd=dvd, div=div):
                svg = build_combined_svg(dvd, div, include_verification=False)
                self.assertTrue(svg.startswith("<svg"), msg=dvd)
                self.assertIn("</svg>", svg)


class TestBuildCombinedWithVerifySmoke(unittest.TestCase):
    def test_matrix(self) -> None:
        for dvd, div in [
            ("1.5", "0.25"),
            ("0.48", "0.016"),
            ("8.75", "2.5"),
        ]:
            with self.subTest(dvd=dvd, div=div):
                svg = build_combined_svg(dvd, div, include_verification=True)
                self.assertIn("验算", svg)
                self.assertTrue(svg.startswith("<svg"))


class TestBuildMultiplicationSvgSmoke(unittest.TestCase):
    def test_with_and_without_verify(self) -> None:
        for verify in (False, True):
            with self.subTest(verify=verify):
                svg = build_multiplication_vertical_svg(
                    "0.016", "30", include_verification=verify
                )
                self.assertTrue(svg.startswith("<svg"))
                if verify:
                    self.assertIn("验算", svg)


class TestBuildAdditionSubtractionIdivSmoke(unittest.TestCase):
    def test_addition(self) -> None:
        for verify in (False, True):
            with self.subTest(verify=verify):
                svg = build_addition_vertical_svg("256", "384", include_verification=verify)
                self.assertTrue(svg.startswith("<svg"))

    def test_subtraction(self) -> None:
        svg = build_subtraction_vertical_svg("100", "1", include_verification=False)
        self.assertTrue(svg.startswith("<svg"))

    def test_integer_division(self) -> None:
        svg = build_integer_division_vertical_svg("144", "12", include_verification=True)
        self.assertIn("验算", svg)
        self.assertTrue(svg.startswith("<svg"))


class TestDividendExtensionRedZeros(unittest.TestCase):
    """续除补在被除数行尾部的 0：与新增小数点同色（如 1÷4 → 1.00）。"""

    def setUp(self) -> None:
        # 与默认 REMARKS_IN_RED=False 不同，本类 SVG 用例需断言 #e02020
        self._save_remark = render_config.REMARKS_IN_RED
        render_config.REMARKS_IN_RED = True

    def tearDown(self) -> None:
        render_config.REMARKS_IN_RED = self._save_remark

    def test_shifted_extension_red_indices(self) -> None:
        self.assertEqual(_dividend_shifted_extension_red_digit_cells("1", 1, 2), [2, 3])
        self.assertEqual(_dividend_cells_shifted_digits("1", 1, 2), ["1", ".", "0", "0"])

    def test_divisor_shift_scale_suffix_red_16_div_0p25(self) -> None:
        cells = list("1600")
        self.assertEqual(
            _divisor_shift_scale_suffix_red_digit_cells(Decimal("16"), "1600", 2, cells),
            [2, 3],
        )

    def test_divisor_shift_scale_suffix_red_12p6_div_0p42(self) -> None:
        cells = list("1260")
        self.assertEqual(
            _divisor_shift_scale_suffix_red_digit_cells(Decimal("12.6"), "1260", 2, cells),
            [3],
        )

    def test_one_div_four_dividend_red_dot_and_zeros(self) -> None:
        svg = build_combined_svg("1", "4", include_verification=False)
        div_main = svg.split("验算", 1)[0]
        self.assertRegex(
            div_main,
            r'(?s)fill="#e02020"[^>]*">\.</text>.*?fill="#e02020"[^>]*">0</text>.*?fill="#e02020"[^>]*">0</text>',
        )

    def test_16_div_0p25_dividend_two_red_zeros(self) -> None:
        svg = build_combined_svg("16", "0.25", include_verification=False)
        div_main = svg.split("验算", 1)[0]
        # 被除数行 1600：末尾两个移位补 0 为红（与除数同行 y_main=48）
        red0_48 = sum(
            1
            for line in div_main.split("\n")
            if 'y="48.00"' in line and 'fill="#e02020"' in line and ">0</text>" in line
        )
        self.assertGreaterEqual(red0_48, 2)

    def test_0p1_div_0p04_dividend_two_red_zeros(self) -> None:
        """pedagogical：对齐 work_ds 的 fp 补零 + 续除补零均标红（0.10→0.100）。"""
        svg = build_combined_svg("0.1", "0.04", include_verification=False)
        div_main = svg.split("验算", 1)[0]
        red0_48 = sum(
            1
            for line in div_main.split("\n")
            if 'y="48.00"' in line and 'fill="#e02020"' in line and ">0</text>" in line
        )
        self.assertGreaterEqual(red0_48, 2)


class TestCombinedSvgVerificationProductSmoke(unittest.TestCase):
    """端到端：组合图可生成；乘法验算块含三位积（防 prod 被误 strip 成一位）。"""

    def test_1p5_div_0p25_with_verify_svg_wellformed(self) -> None:
        svg = build_combined_svg("1.5", "0.25", include_verification=True)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("验算", svg)
        self.assertGreaterEqual(svg.count('dominant-baseline="middle">.</text>'), 2)

    def test_multiplication_verify_contains_three_digit_product(self) -> None:
        svg = build_multiplication_vertical_svg("25", "4", include_verification=True)
        self.assertRegex(
            svg,
            r">1</text>[^<]*<text[^>]+>0</text>[^<]*<text[^>]+>0</text>",
        )


if __name__ == "__main__":
    unittest.main()
