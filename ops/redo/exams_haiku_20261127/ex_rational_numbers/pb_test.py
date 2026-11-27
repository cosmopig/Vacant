import math
import numbers

import pytest
from rational_numbers import Rational


def test_numerator_and_denominator_are_integers():
    """REQ: "A rational number is defined as the quotient of two integers `a` and `b`, called the numerator and denominator, respectively, where `b != 0`."

    Property: a constructed Rational exposes its numerator and denominator as integers.
    """
    r = Rational(3, 5)
    assert isinstance(r.numer, int)
    assert isinstance(r.denom, int)
    assert (r.numer, r.denom) == (3, 5)


def test_reduces_examples_from_text():
    """REQ: "For example, `4/4` should reduce to `1/1`, `30/60` should reduce to `1/2`, `12/8` should reduce to `3/2`, etc."

    Property: the three examples given in the text reduce to the stated lowest terms.
    """
    r = Rational(4, 4)
    assert (r.numer, r.denom) == (1, 1)

    r = Rational(30, 60)
    assert (r.numer, r.denom) == (1, 2)

    r = Rational(12, 8)
    assert (r.numer, r.denom) == (3, 2)


def test_always_reduced_to_lowest_terms():
    """REQ: "Your implementation of rational numbers should always be reduced to lowest terms."

    Property: for a range of inputs, the stored value is in lowest terms and in standard form.
    """
    cases = [
        ((6, 9), (2, 3)),
        ((-6, 9), (-2, 3)),
        ((10, -15), (-2, 3)),
        ((0, 7), (0, 1)),
        ((18, -24), (-3, 4)),
        ((7, 13), (7, 13)),
        ((100, 75), (4, 3)),
    ]
    for (a, b), (en, ed) in cases:
        r = Rational(a, b)
        assert (r.numer, r.denom) == (en, ed), f"Rational({a}, {b})"
        assert r.denom > 0
        assert math.gcd(abs(r.numer), r.denom) == 1


def test_negative_denominator_example_from_text():
    """REQ: "For example, `3/-4` should be reduced to `-3/4`"

    Property: a negative denominator is moved to the numerator, giving standard form.
    """
    r = Rational(3, -4)
    assert (r.numer, r.denom) == (-3, 4)


def test_standard_form_when_both_negative():
    """REQ: "If a denominator with a negative integer is present, multiply both numerator and denominator by `-1` to ensure standard form is reached."

    Property: when numerator and denominator are both negative, the sign cancels and the denominator stays positive.
    """
    r = Rational(-3, -4)
    assert (r.numer, r.denom) == (3, 4)

    r = Rational(-8, -2)
    assert (r.numer, r.denom) == (4, 1)


def test_zero_numerator_reduces_to_zero_over_one():
    """REQ: "To reduce a rational number `r = a/b`, divide `a` and `b` by the greatest common divisor (gcd) of `a` and `b`."

    Property: with a = 0, gcd(0, b) = |b|, so the value reduces to 0/1 regardless of the sign of b.
    """
    r = Rational(0, 7)
    assert (r.numer, r.denom) == (0, 1)

    r = Rational(0, -7)
    assert (r.numer, r.denom) == (0, 1)


def test_equal_values_compare_equal():
    """REQ: "Your implementation of rational numbers should always be reduced to lowest terms."

    Property: rationals with the same value compare equal, and different values compare unequal.
    """
    assert Rational(1, 2) == Rational(-2, -4)
    assert Rational(1, -2) == Rational(-1, 2)
    assert Rational(1, 2) != Rational(1, 3)


def test_absolute_value():
    """REQ: "The absolute value `|r|` of the rational number `r = a/b` is equal to `|a|/|b|`."

    Property: abs(r) equals |a|/|b| in lowest terms.
    """
    r = abs(Rational(-3, 4))
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (3, 4)

    r = abs(Rational(3, -4))
    assert (r.numer, r.denom) == (3, 4)

    r = abs(Rational(-3, -4))
    assert (r.numer, r.denom) == (3, 4)

    r = abs(Rational(0, 5))
    assert (r.numer, r.denom) == (0, 1)


def test_addition():
    """REQ: "The sum of two rational numbers `r₁ = a₁/b₁` and `r₂ = a₂/b₂` is `r₁ + r₂ = a₁/b₁ + a₂/b₂ = (a₁ * b₂ + a₂ * b₁) / (b₁ * b₂)`."

    Property: addition follows the stated formula and the result is reduced.
    """
    r = Rational(1, 2) + Rational(1, 3)
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (5, 6)

    r = Rational(-1, 2) + Rational(1, 3)
    assert (r.numer, r.denom) == (-1, 6)

    r = Rational(1, 2) + Rational(1, 2)
    assert (r.numer, r.denom) == (1, 1)


def test_subtraction():
    """REQ: "The difference of two rational numbers `r₁ = a₁/b₁` and `r₂ = a₂/b₂` is `r₁ - r₂ = a₁/b₁ - a₂/b₂ = (a₁ * b₂ - a₂ * b₁) / (b₁ * b₂)`."

    Property: subtraction follows the stated formula, keeps a positive denominator, and is reduced.
    """
    r = Rational(1, 2) - Rational(1, 3)
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (1, 6)

    r = Rational(1, 3) - Rational(1, 2)
    assert (r.numer, r.denom) == (-1, 6)

    r = Rational(1, 2) - Rational(1, 2)
    assert (r.numer, r.denom) == (0, 1)


def test_multiplication():
    """REQ: "The product (multiplication) of two rational numbers `r₁ = a₁/b₁` and `r₂ = a₂/b₂` is `r₁ * r₂ = (a₁ * a₂) / (b₁ * b₂)`."

    Property: multiplication follows the stated formula, including sign handling, and is reduced.
    """
    r = Rational(2, 3) * Rational(3, 4)
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (1, 2)

    r = Rational(-2, 3) * Rational(3, -4)
    assert (r.numer, r.denom) == (1, 2)

    r = Rational(2, 3) * Rational(-3, 4)
    assert (r.numer, r.denom) == (-1, 2)


def test_division():
    """REQ: "Dividing a rational number `r₁ = a₁/b₁` by another `r₂ = a₂/b₂` is `r₁ / r₂ = (a₁ * b₂) / (a₂ * b₁)` if `a₂` is not zero."

    Property: division follows the stated formula when the divisor's numerator is nonzero.
    """
    r = Rational(1, 2) / Rational(1, 4)
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (2, 1)

    r = Rational(1, 2) / Rational(-1, 4)
    assert (r.numer, r.denom) == (-2, 1)

    r = Rational(2, 3) / Rational(4, 9)
    assert (r.numer, r.denom) == (3, 2)


def test_power_to_non_negative_integer():
    """REQ: "Exponentiation of a rational number `r = a/b` to a non-negative integer power `n` is `r^n = (a^n)/(b^n)`."

    Property: r**n for n >= 0 equals a**n / b**n, reduced.
    """
    r = Rational(2, 3) ** 2
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (4, 9)

    r = Rational(-2, 3) ** 3
    assert (r.numer, r.denom) == (-8, 27)

    r = Rational(2, 3) ** 0
    assert (r.numer, r.denom) == (1, 1)


def test_power_to_negative_integer():
    """REQ: "Exponentiation of a rational number `r = a/b` to a negative integer power `n` is `r^n = (b^m)/(a^m)`, where `m = |n|`."

    Property: r**n for n < 0 equals b**|n| / a**|n|, in standard form and reduced.
    """
    r = Rational(2, 3) ** -2
    assert isinstance(r, Rational)
    assert (r.numer, r.denom) == (9, 4)

    r = Rational(-2, 3) ** -1
    assert (r.numer, r.denom) == (-3, 2)

    r = Rational(5, 1) ** -1
    assert (r.numer, r.denom) == (1, 5)


def test_power_to_real_float_exponent():
    """REQ: "Exponentiation of a rational number `r = a/b` to a real (floating-point) number `x` is the quotient `(a^x)/(b^x)`, which is a real number."

    Property: r**x for a float x gives a real number equal to a**x / b**x.
    """
    r = Rational(4, 9) ** 0.5
    assert isinstance(r, numbers.Real)
    assert r == pytest.approx(2 / 3, rel=1e-9)

    r = Rational(4, 9) ** 1.5
    assert isinstance(r, numbers.Real)
    assert r == pytest.approx(8 / 27, rel=1e-9)


def test_real_base_to_rational_power():
    """REQ: "Exponentiation of a real number `x` to a rational number `r = a/b` is `x^(a/b) = root(x^a, b)`, where `root(p, q)` is the `q`th root of `p`."

    Property: x ** (a/b) equals the b-th root of x**a, computed via __rpow__.
    """
    result = 2 ** Rational(1, 2)
    assert isinstance(result, numbers.Real)
    assert result == pytest.approx(1.41421356237, rel=1e-9)

    result = 8 ** Rational(2, 3)
    assert isinstance(result, numbers.Real)
    assert result == pytest.approx(4.0, rel=1e-9)


def test_operation_results_reduced_and_standard_form():
    """REQ: "If a denominator with a negative integer is present, multiply both numerator and denominator by `-1` to ensure standard form is reached."

    Property: results of +, -, *, /, and ** on unreduced or negative-denominator inputs are reduced and have a positive denominator.
    """
    pairs = [
        (Rational(2, 4), Rational(-3, 6)),
        (Rational(1, -3), Rational(5, 10)),
        (Rational(-4, 6), Rational(9, -12)),
    ]
    for x, y in pairs:
        results = [x + y, x - y, x * y, x / y]
        for r in results:
            assert r.denom > 0
            assert math.gcd(abs(r.numer), r.denom) == 1

    for x, _ in pairs:
        for r in [x ** 2, x ** -2, x ** -3]:
            assert r.denom > 0
            assert math.gcd(abs(r.numer), r.denom) == 1


def test_operations_return_rational():
    """REQ: "Implement the following operations: addition, subtraction, multiplication and division of two rational numbers, absolute value, exponentiation of a given rational number to an integer power, exponentiation of a given rational number to a real (floating-point) power, exponentiation of a real number to a rational number."

    Property: the rational-valued operations on rational operands return Rational instances.
    """
    r = Rational(1, 2)
    s = Rational(-2, 3)
    assert isinstance(r + s, Rational)
    assert isinstance(r - s, Rational)
    assert isinstance(r * s, Rational)
    assert isinstance(r / s, Rational)
    assert isinstance(abs(s), Rational)
    assert isinstance(r ** 3, Rational)
    assert isinstance(s ** -1, Rational)
