import pytest

from rational_numbers import Rational


def test_reduces_to_lowest_terms():
    r = Rational(4, 4)
    assert (r.numer, r.denom) == (1, 1)
    r = Rational(30, 60)
    assert (r.numer, r.denom) == (1, 2)
    r = Rational(12, 8)
    assert (r.numer, r.denom) == (3, 2)


def test_zero_numerator_reduces_to_zero_over_one():
    r = Rational(0, 5)
    assert (r.numer, r.denom) == (0, 1)


def test_negative_denominator_moves_sign_to_numerator():
    r = Rational(3, -4)
    assert (r.numer, r.denom) == (-3, 4)


def test_both_negative_gives_positive_standard_form():
    r = Rational(-3, -4)
    assert (r.numer, r.denom) == (3, 4)


def test_equal_rationals_in_different_unreduced_forms_are_equal():
    assert Rational(2, 4) == Rational(1, 2)


def test_addition():
    assert Rational(1, 2) + Rational(1, 3) == Rational(5, 6)


def test_subtraction():
    assert Rational(1, 2) - Rational(1, 3) == Rational(1, 6)
    assert Rational(1, 3) - Rational(1, 2) == Rational(-1, 6)


def test_multiplication():
    assert Rational(2, 3) * Rational(3, 4) == Rational(1, 2)


def test_division():
    assert Rational(1, 2) / Rational(3, 4) == Rational(2, 3)
    assert Rational(1, 2) / Rational(-1, 3) == Rational(-3, 2)


def test_absolute_value():
    assert abs(Rational(-1, 2)) == Rational(1, 2)
    assert abs(Rational(1, -2)) == Rational(1, 2)
    assert abs(Rational(3, 7)) == Rational(3, 7)


def test_power_non_negative_integer():
    assert Rational(2, 3) ** 2 == Rational(4, 9)
    assert Rational(2, 3) ** 0 == Rational(1, 1)


def test_power_negative_integer_inverts_base():
    assert Rational(2, 3) ** -2 == Rational(9, 4)


def test_power_real_exponent_returns_real_number():
    assert Rational(1, 4) ** 0.5 == pytest.approx(0.5)


def test_real_base_to_rational_power():
    assert 2 ** Rational(1, 2) == pytest.approx(2 ** 0.5)
    assert 2 ** Rational(3, 1) == pytest.approx(8)
