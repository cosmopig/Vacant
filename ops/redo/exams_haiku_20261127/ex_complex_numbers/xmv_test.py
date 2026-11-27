import math

import pytest

from complex_numbers import ComplexNumber


def test_equality_of_complex_numbers():
    # SRC: "A **complex number** is expressed in the form `z = a + b * i`, where:"
    assert ComplexNumber(1, 2) == ComplexNumber(1, 2)
    # SRC: "A **complex number** is expressed in the form `z = a + b * i`, where:"
    assert ComplexNumber(1, 2) != ComplexNumber(2, 1)


def test_addition():
    # SRC: "The sum of two complex numbers `z1 = a + b * i` and `z2 = c + d * i` is computed by adding their real and imaginary parts separately:"
    assert ComplexNumber(1, 2) + ComplexNumber(3, 4) == ComplexNumber(4, 6)
    # SRC: "= (a + c) + (b + d) * i"
    assert ComplexNumber(1, 2) + ComplexNumber(-1, -2) == ComplexNumber(0, 0)


def test_subtraction():
    # SRC: "The difference of two complex numbers is obtained by subtracting their respective parts:"
    assert ComplexNumber(5, 3) - ComplexNumber(2, 7) == ComplexNumber(3, -4)
    # SRC: "z1 - z2 = (a + b * i) - (c + d * i)"
    assert ComplexNumber(2, 3) - ComplexNumber(2, 3) == ComplexNumber(0, 0)


def test_multiplication():
    # SRC: "The product of two complex numbers is defined as:"
    assert ComplexNumber(1, 2) * ComplexNumber(3, 4) == ComplexNumber(-5, 10)
    # SRC: "= (a * c - b * d) + (b * c + a * d) * i"
    assert ComplexNumber(0, 1) * ComplexNumber(0, 1) == ComplexNumber(-1, 0)


def test_conjugate():
    # SRC: "The conjugate of the complex number `z = a + b * i` is given by:"
    assert ComplexNumber(3, 4).conjugate() == ComplexNumber(3, -4)
    # SRC: "zc = a - b * i"
    assert ComplexNumber(5, 0).conjugate() == ComplexNumber(5, 0)


def test_square_of_absolute_value_is_z_times_conjugate():
    # SRC: "|z|^2 = z * zc = a^2 + b^2"
    assert ComplexNumber(3, 4) * ComplexNumber(3, 4).conjugate() == ComplexNumber(25, 0)


def test_absolute_value():
    # SRC: "The absolute value (or modulus) of `z` is defined as:"
    assert abs(ComplexNumber(3, 4)) == pytest.approx(5)
    # SRC: "|z| = sqrt(a^2 + b^2)"
    assert abs(ComplexNumber(-3, -4)) == pytest.approx(5)
    # SRC: "|z| = sqrt(a^2 + b^2)"
    assert abs(ComplexNumber(0, 0)) == pytest.approx(0)
    # SRC: "|z| = sqrt(a^2 + b^2)"
    assert abs(ComplexNumber(0, -2)) == pytest.approx(2)


def test_reciprocal_via_division():
    # SRC: "1 / z = 1 / (a + b * i)"
    assert ComplexNumber(1, 0) / ComplexNumber(2, 0) == ComplexNumber(0.5, 0)
    # SRC: "The reciprocal of a non-zero complex number is given by:"
    assert ComplexNumber(1, 0) / ComplexNumber(0, 2) == ComplexNumber(0, -0.5)


def test_division():
    # SRC: "= (a * c + b * d) / (c^2 + d^2) + (b * c - a * d) / (c^2 + d^2) * i"
    assert ComplexNumber(1, 1) / ComplexNumber(1, -1) == ComplexNumber(0, 1)
    # SRC: "z1 / z2 = z1 * (1 / z2)"
    assert ComplexNumber(-2, 4) / ComplexNumber(0, 2) == ComplexNumber(2, 1)
    # SRC: "The division of one complex number by another is given by:"
    assert ComplexNumber(2, 0) / ComplexNumber(2, 0) == ComplexNumber(1, 0)
    # SRC: "The division of one complex number by another is given by:"
    assert ComplexNumber(5, 2) / ComplexNumber(1, 1) == ComplexNumber(3.5, -1.5)


def test_exponentiation_of_e():
    # SRC: "Raising _e_ (the base of the natural logarithm) to a complex exponent can be expressed using Euler's formula:"
    assert ComplexNumber(0, 0).exp() == ComplexNumber(1, 0)
    # SRC: "e^(a + b * i) = e^a * e^(b * i)"
    assert abs(ComplexNumber(1, 0).exp()) == pytest.approx(math.e)
    # SRC: "e^(a + b * i) = e^a * e^(b * i)"
    assert abs(ComplexNumber(0, math.pi).exp()) == pytest.approx(1)
    # SRC: "e^(a + b * i) = e^a * e^(b * i)"
    assert abs(ComplexNumber(2, 1.5).exp()) == pytest.approx(math.exp(2))
