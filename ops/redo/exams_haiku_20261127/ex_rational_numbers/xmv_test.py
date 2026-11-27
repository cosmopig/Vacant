import pytest

from rational_numbers import Rational


def test_reduces_equal_numerator_and_denominator_to_one():
    r = Rational(4, 4)
    # SRC: "For example, `4/4` should reduce to `1/1`, `30/60` should reduce to `1/2`, `12/8` should reduce to `3/2`, etc."
    assert r.numer == 1
    # SRC: "For example, `4/4` should reduce to `1/1`, `30/60` should reduce to `1/2`, `12/8` should reduce to `3/2`, etc."
    assert r.denom == 1


def test_reduces_30_over_60_to_one_half():
    r = Rational(30, 60)
    # SRC: "Your implementation of rational numbers should always be reduced to lowest terms."
    assert r.numer == 1
    # SRC: "Your implementation of rational numbers should always be reduced to lowest terms."
    assert r.denom == 2


def test_reduces_12_over_8_to_three_halves():
    r = Rational(12, 8)
    # SRC: "To reduce a rational number `r = a/b`, divide `a` and `b` by the greatest common divisor (gcd) of `a` and `b`."
    assert r.numer == 3
    # SRC: "To reduce a rational number `r = a/b`, divide `a` and `b` by the greatest common divisor (gcd) of `a` and `b`."
    assert r.denom == 2


def test_moves_negative_sign_to_numerator():
    r = Rational(3, -4)
    # SRC: "For example, `3/-4` should be reduced to `-3/4`"
    assert r.numer == -3
    # SRC: "For example, `3/-4` should be reduced to `-3/4`"
    assert r.denom == 4


def test_denominator_is_positive_when_both_negative():
    r = Rational(-3, -4)
    # SRC: "the denominator should always be a positive integer"
    assert r.numer == 3
    # SRC: "the denominator should always be a positive integer"
    assert r.denom == 4


def test_zero_numerator_reduces_to_zero_over_one():
    r = Rational(0, 5)
    # SRC: "To reduce a rational number `r = a/b`, divide `a` and `b` by the greatest common divisor (gcd) of `a` and `b`."
    assert r.numer == 0
    # SRC: "To reduce a rational number `r = a/b`, divide `a` and `b` by the greatest common divisor (gcd) of `a` and `b`."
    assert r.denom == 1


def test_addition_of_two_rationals():
    # SRC: "The sum of two rational numbers"
    assert Rational(1, 2) + Rational(1, 3) == Rational(5, 6)


def test_addition_with_negative_result():
    # SRC: "The sum of two rational numbers"
    assert Rational(-1, 2) + Rational(1, 3) == Rational(-1, 6)


def test_subtraction_of_two_rationals():
    # SRC: "The difference of two rational numbers"
    assert Rational(1, 2) - Rational(1, 3) == Rational(1, 6)


def test_multiplication_of_two_rationals():
    # SRC: "The product (multiplication) of two rational numbers"
    assert Rational(2, 3) * Rational(3, 4) == Rational(1, 2)


def test_division_of_two_rationals():
    # SRC: "Dividing a rational number `r₁ = a₁/b₁` by another `r₂ = a₂/b₂` is `r₁ / r₂ = (a₁ * b₂) / (a₂ * b₁)` if `a₂` is not zero."
    assert Rational(1, 2) / Rational(3, 4) == Rational(2, 3)


def test_division_by_negative_rational_gives_standard_form():
    r = Rational(1, 2) / Rational(-1, 4)
    # SRC: "the denominator should always be a positive integer"
    assert r.numer == -2
    # SRC: "the denominator should always be a positive integer"
    assert r.denom == 1


def test_absolute_value_of_negative_rational():
    # SRC: "The absolute value `|r|` of the rational number `r = a/b` is equal to `|a|/|b|`."
    assert abs(Rational(-3, 4)) == Rational(3, 4)


def test_absolute_value_of_rational_with_negative_denominator():
    # SRC: "The absolute value `|r|` of the rational number `r = a/b` is equal to `|a|/|b|`."
    assert abs(Rational(3, -4)) == Rational(3, 4)


def test_power_with_non_negative_integer_exponent():
    # SRC: "Exponentiation of a rational number `r = a/b` to a non-negative integer power `n` is `r^n = (a^n)/(b^n)`."
    assert Rational(2, 3) ** 2 == Rational(4, 9)


def test_power_zero_is_one():
    # SRC: "Exponentiation of a rational number `r = a/b` to a non-negative integer power `n` is `r^n = (a^n)/(b^n)`."
    assert Rational(2, 3) ** 0 == Rational(1, 1)


def test_power_of_negative_base_with_odd_exponent():
    # SRC: "Exponentiation of a rational number `r = a/b` to a non-negative integer power `n` is `r^n = (a^n)/(b^n)`."
    assert Rational(-2, 3) ** 3 == Rational(-8, 27)


def test_power_with_negative_integer_exponent():
    # SRC: "Exponentiation of a rational number `r = a/b` to a negative integer power `n` is `r^n = (b^m)/(a^m)`, where `m = |n|`."
    assert Rational(2, 3) ** -2 == Rational(9, 4)


def test_power_with_real_exponent_returns_real_number():
    # SRC: "Exponentiation of a rational number `r = a/b` to a real (floating-point) number `x` is the quotient"
    assert Rational(1, 4) ** 0.5 == pytest.approx(0.5)


def test_power_with_real_exponent_on_square_rational():
    # SRC: "Exponentiation of a rational number `r = a/b` to a real (floating-point) number `x` is the quotient"
    assert Rational(4, 9) ** 0.5 == pytest.approx(2 / 3)


def test_real_base_to_rational_power_square_root():
    # SRC: "Exponentiation of a real number `x` to a rational number `r = a/b` is `x^(a/b) = root(x^a, b)`"
    assert 4 ** Rational(1, 2) == pytest.approx(2.0)


def test_real_base_to_rational_power_cube_root():
    # SRC: "Exponentiation of a real number `x` to a rational number `r = a/b` is `x^(a/b) = root(x^a, b)`"
    assert 8 ** Rational(2, 3) == pytest.approx(4.0)


def test_real_base_to_rational_power_improper_fraction():
    # SRC: "Exponentiation of a real number `x` to a rational number `r = a/b` is `x^(a/b) = root(x^a, b)`"
    assert 4 ** Rational(3, 2) == pytest.approx(8.0)
