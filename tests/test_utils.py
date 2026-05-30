"""Tests for mlb.utils — pure numeric coercion helpers."""

import unittest

from mlb.utils import ip_to_float, to_float


class ToFloatTests(unittest.TestCase):
    def test_parses_numeric_string(self):
        self.assertEqual(to_float("3.14"), 3.14)

    def test_parses_int_and_float(self):
        self.assertEqual(to_float(5), 5.0)
        self.assertEqual(to_float(2.5), 2.5)

    def test_none_returns_default(self):
        self.assertEqual(to_float(None), 0.0)

    def test_bad_string_returns_default(self):
        self.assertEqual(to_float("abc"), 0.0)

    def test_empty_string_returns_default(self):
        self.assertEqual(to_float(""), 0.0)

    def test_custom_default_used(self):
        self.assertEqual(to_float(None, default=-1.0), -1.0)
        self.assertEqual(to_float("nope", default=-1.0), -1.0)

    def test_custom_default_not_used_when_parseable(self):
        self.assertEqual(to_float("7", default=-1.0), 7.0)


class IpToFloatTests(unittest.TestCase):
    def test_whole_innings(self):
        self.assertEqual(ip_to_float("6"), 6.0)
        self.assertEqual(ip_to_float("6.0"), 6.0)

    def test_one_out(self):
        self.assertAlmostEqual(ip_to_float("6.1"), 6 + 1 / 3.0)

    def test_two_outs(self):
        self.assertAlmostEqual(ip_to_float("6.2"), 6 + 2 / 3.0)

    def test_accepts_float_input(self):
        self.assertAlmostEqual(ip_to_float(7.2), 7 + 2 / 3.0)

    def test_zero(self):
        self.assertEqual(ip_to_float("0"), 0.0)

    def test_none_returns_zero(self):
        self.assertEqual(ip_to_float(None), 0.0)

    def test_garbage_returns_zero(self):
        self.assertEqual(ip_to_float("abc"), 0.0)


if __name__ == "__main__":
    unittest.main()
