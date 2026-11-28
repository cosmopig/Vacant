"""Acceptance tests for the complex_numbers exercise.

Each test_ function checks one property stated (or clearly implied) by the
requirements text. Expected values were derived by hand from the formulas
in the requirements, not by calling the solution.
"""
import math
import numbers

import pytest

from complex_numbers import ComplexNumber

TOLERANCE = 1e-9


def _close(z, w):
    """Return True if complex numbers z and w differ by less than TOLERANCE."""
    return abs(z - w) < TOLERANCE


def test_constructor_accepts_real_and_integer_parts():
    """REQ: "A **complex number** is expressed in the form `z = a + b * i`, where:"

    Parts may be integers or floats, and equal parts compare equal while
    different parts compare unequal.
    """
    z = ComplexNumber(1, 2)
    assert z == ComplexNumber(1, 2)
    assert ComplexNumber(1.5, -2.0) == ComplexNumber(1.5, -2.0)
    assert z != ComplexNumber(1, 3)
    assert z != ComplexNumber(2, 1)
    assert ComplexNumber(0, 0) != ComplexNumber(1, 0)


def test_conjugate_negates_imaginary_part():
    """REQ: "The conjugate of the complex number `z = a + b * i` is given by:"

    Example: conjugate of 1 + 2i is 1 - 2i; of -3 - 5i is -3 + 5i.
    """
    assert ComplexNumber(1, 2).conjugate() == ComplexNumber(1, -2)
    assert ComplexNumber(-3, -5).conjugate() == ComplexNumber(-3, 5)


def test_conjugate_of_real_number_is_itself():
    """REQ: "The conjugate of the complex number `z = a + b * i` is given by:"

    Boundary: when b = 0, the conjugate equals the original number.
    """
    assert ComplexNumber(4, 0).conjugate() == ComplexNumber(4, 0)


def test_conjugate_twice_returns_original():
    """REQ: "The conjugate of the complex number `z = a + b * i` is given by:"

    Invariant: conjugating twice gives back the original number.
    """
    z = ComplexNumber(2.5, -7)
    assert z.conjugate().conjugate() == z


def test_absolute_value_example_3_4_is_5():
    """REQ: "The absolute value (or modulus) of `z` is defined as:"

    Examples: |3 + 4i| = 5, |-3 + 4i| = 5, |0 - 2i| = 2.
    """
    assert abs(ComplexNumber(3, 4)) == pytest.approx(5.0)
    assert abs(ComplexNumber(-3, 4)) == pytest.approx(5.0)
    assert abs(ComplexNumber(0, -2)) == pytest.approx(2.0)


def test_absolute_value_is_real_nonnegative_and_conjugate_invariant():
    """REQ: "The absolute value (or modulus) of `z` is defined as:"

    The result is a non-negative real number, zero for 0 + 0i, and equal
    for z and its conjugate.
    """
    z = ComplexNumber(-1.5, 2)
    value = abs(z)
    assert isinstance(value, numbers.Real)
    assert value >= 0
    assert abs(ComplexNumber(0, 0)) == pytest.approx(0.0)
    assert abs(z.conjugate()) == pytest.approx(value)


def test_square_of_absolute_value_equals_z_times_conjugate():
    """REQ: "The square of the absolute value is computed as the product of `z` and its conjugate `zc`:"

    Example: z = 3 + 4i gives z * zc = 25 + 0i and |z|^2 = 25.
    """
    z = ComplexNumber(3, 4)
    assert z * z.conjugate() == ComplexNumber(25, 0)
    assert abs(z) ** 2 == pytest.approx(25.0)


def test_addition_example():
    """REQ: "The sum of two complex numbers `z1 = a + b * i` and `z2 = c + d * i` is computed by adding their real and imaginary parts separately:"

    Examples: (1 + 2i) + (3 + 4i) = 4 + 6i; (-1 + 5i) + (2 - 7i) = 1 - 2i.
    """
    assert ComplexNumber(1, 2) + ComplexNumber(3, 4) == ComplexNumber(4, 6)
    assert ComplexNumber(-1, 5) + ComplexNumber(2, -7) == ComplexNumber(1, -2)


def test_addition_is_commutative():
    """REQ: "The sum of two complex numbers `z1 = a + b * i` and `z2 = c + d * i` is computed by adding their real and imaginary parts separately:"

    Invariant: z1 + z2 equals z2 + z1.
    """
    z1 = ComplexNumber(1.5, -2)
    z2 = ComplexNumber(3, 4)
    assert z1 + z2 == z2 + z1


def test_adding_zero_is_identity():
    """REQ: "The sum of two complex numbers `z1 = a + b * i` and `z2 = c + d * i` is computed by adding their real and imaginary parts separately:"

    Boundary: adding 0 + 0i on either side leaves the number unchanged.
    """
    z = ComplexNumber(6, -1)
    zero = ComplexNumber(0, 0)
    assert z + zero == z
    assert zero + z == z


def test_subtraction_example():
    """REQ: "The difference of two complex numbers is obtained by subtracting their respective parts:"

    Examples: (1 + 2i) - (3 + 4i) = -2 - 2i; (5 - 1i) - (2 + 3i) = 3 - 4i.
    """
    assert ComplexNumber(1, 2) - ComplexNumber(3, 4) == ComplexNumber(-2, -2)
    assert ComplexNumber(5, -1) - ComplexNumber(2, 3) == ComplexNumber(3, -4)


def test_subtraction_of_number_from_itself_is_zero():
    """REQ: "The difference of two complex numbers is obtained by subtracting their respective parts:"

    Boundary: z - z = 0 + 0i.
    """
    z = ComplexNumber(3, -4)
    assert z - z == ComplexNumber(0, 0)


def test_multiplication_example():
    """REQ: "The product of two complex numbers is defined as:"

    Examples: (1 + 2i) * (3 + 4i) = -5 + 10i; (2 - 1i) * (-3 + 5i) = -1 + 13i.
    """
    assert ComplexNumber(1, 2) * ComplexNumber(3, 4) == ComplexNumber(-5, 10)
    assert ComplexNumber(2, -1) * ComplexNumber(-3, 5) == ComplexNumber(-1, 13)


def test_multiplication_is_commutative():
    """REQ: "The product of two complex numbers is defined as:"

    Invariant: z1 * z2 equals z2 * z1.
    """
    z1 = ComplexNumber(2, -1)
    z2 = ComplexNumber(-3, 5)
    assert z1 * z2 == z2 * z1


def test_multiplication_by_imaginary_unit_rotates_by_quarter_turn():
    """REQ: "The product of two complex numbers is defined as:"

    Example: (3 + 4i) * i = -4 + 3i, since i is 0 + 1i.
    """
    assert ComplexNumber(3, 4) * ComplexNumber(0, 1) == ComplexNumber(-4, 3)


def test_division_example():
    """REQ: "The division of one complex number by another is given by:"

    Example: (1 + 2i) / (3 + 4i) = 11/25 + (2/25) i = 0.44 + 0.08i.
    """
    result = ComplexNumber(1, 2) / ComplexNumber(3, 4)
    assert _close(result, ComplexNumber(0.44, 0.08))


def test_division_by_nonzero_pure_imaginary_and_pure_real():
    """REQ: "The reciprocal of a non-zero complex number is given by:"

    Boundary: divisors with a zero real part or a zero imaginary part are
    valid non-zero divisors. Examples: 1 / i = -i; (3 + 4i) / 2 = 1.5 + 2i.
    """
    assert _close(ComplexNumber(1, 0) / ComplexNumber(0, 1), ComplexNumber(0, -1))
    assert _close(ComplexNumber(3, 4) / ComplexNumber(2, 0), ComplexNumber(1.5, 2))


def test_division_of_number_by_itself_is_one():
    """REQ: "The division of one complex number by another is given by:"

    Boundary: z / z = 1 + 0i for non-zero z.
    """
    z = ComplexNumber(3, 4)
    assert _close(z / z, ComplexNumber(1, 0))


def test_reciprocal_example():
    """REQ: "The reciprocal of a non-zero complex number is given by:"

    Example: 1 / (3 + 4i) = 3/25 - (4/25) i = 0.12 - 0.16i.
    """
    result = ComplexNumber(1, 0) / ComplexNumber(3, 4)
    assert _close(result, ComplexNumber(0.12, -0.16))


def test_number_times_its_reciprocal_is_one():
    """REQ: "The reciprocal of a non-zero complex number is given by:"

    Invariant: z * (1 / z) = 1 + 0i for non-zero z.
    """
    z = ComplexNumber(3, 4)
    assert _close(z * (ComplexNumber(1, 0) / z), ComplexNumber(1, 0))


def test_division_equals_multiplication_by_reciprocal():
    """REQ: "`z1 / z2 = z1 * (1 / z2)`"

    Invariant: dividing z1 by z2 gives the same result as multiplying z1
    by the reciprocal of z2.
    """
    z1 = ComplexNumber(1, 2)
    z2 = ComplexNumber(3, 4)
    assert _close(z1 / z2, z1 * (ComplexNumber(1, 0) / z2))


def test_exp_of_zero_is_one():
    """REQ: "Raising _e_ (the base of the natural logarithm) to a complex exponent can be expressed using Euler's formula:"

    Boundary: e^(0 + 0i) = 1.
    """
    assert _close(ComplexNumber(0, 0).exp(), ComplexNumber(1, 0))


def test_exp_of_real_exponent_is_ordinary_exponential():
    """REQ: "Raising _e_ (the base of the natural logarithm) to a complex exponent can be expressed using Euler's formula:"

    With b = 0, e^(a + 0i) = e^a. Examples: e^1 = e; e^-2 = exp(-2).
    """
    assert _close(ComplexNumber(1, 0).exp(), ComplexNumber(math.e, 0))
    assert _close(ComplexNumber(-2, 0).exp(), ComplexNumber(math.exp(-2), 0))


def test_euler_identity_exp_of_i_pi_is_minus_one():
    """REQ: "`e^(a + b * i) = e^a * (cos(b) + i * sin(b))`"

    With a = 0 and b = pi, e^(i*pi) = -1 + 0i.
    """
    assert _close(ComplexNumber(0, math.pi).exp(), ComplexNumber(-1, 0))


def test_exp_of_pure_imaginary_is_cos_plus_i_sin():
    """REQ: "`e^(a + b * i) = e^a * (cos(b) + i * sin(b))`"

    With a = 0, e^(i*b) = cos(b) + i*sin(b). Example: b = 1.
    The result also has modulus 1 for any real b.
    """
    assert _close(ComplexNumber(0, 1.0).exp(), ComplexNumber(math.cos(1.0), math.sin(1.0)))
    assert abs(ComplexNumber(0, 2.5).exp()) == pytest.approx(1.0, abs=TOLERANCE)


def test_exp_adds_exponents():
    """REQ: "`e^(a + b * i) = e^a * e^(b * i)`"

    Invariant: e^(z1 + z2) equals e^z1 * e^z2.
    """
    z1 = ComplexNumber(0.5, 1.0)
    z2 = ComplexNumber(1.25, -0.75)
    assert _close((z1 + z2).exp(), z1.exp() * z2.exp())


def test_arithmetic_results_are_complex_numbers():
    """REQ: "Given that you should not use built-in support for complex numbers, implement the following operations:"

    Each operation returns a ComplexNumber, and abs returns a real number.
    """
    z1 = ComplexNumber(1, 2)
    z2 = ComplexNumber(3, 4)
    assert isinstance(z1 + z2, ComplexNumber)
    assert isinstance(z1 - z2, ComplexNumber)
    assert isinstance(z1 * z2, ComplexNumber)
    assert isinstance(z1 / z2, ComplexNumber)
    assert isinstance(z1.conjugate(), ComplexNumber)
    assert isinstance(z1.exp(), ComplexNumber)
    assert isinstance(abs(z1), numbers.Real)
