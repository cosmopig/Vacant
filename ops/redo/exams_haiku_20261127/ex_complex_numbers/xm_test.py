import math

import pytest

from complex_numbers import ComplexNumber

TOL = 1e-9


def assert_close(z, real, imaginary):
    """Check that complex number z equals real + imaginary*i within TOL."""
    diff = z - ComplexNumber(real, imaginary)
    assert abs(diff) < TOL


def test_equality_compares_both_parts():
    assert ComplexNumber(1, 2) == ComplexNumber(1, 2)
    assert not (ComplexNumber(1, 2) == ComplexNumber(2, 1))


def test_conjugate_negates_imaginary_part():
    assert ComplexNumber(3, 4).conjugate() == ComplexNumber(3, -4)
    assert ComplexNumber(-3, -4).conjugate() == ComplexNumber(-3, 4)
    assert ComplexNumber(3, 0).conjugate() == ComplexNumber(3, 0)


def test_absolute_value():
    assert abs(ComplexNumber(3, 4)) == pytest.approx(5)
    assert abs(ComplexNumber(-3, -4)) == pytest.approx(5)
    assert abs(ComplexNumber(0, 1)) == pytest.approx(1)
    assert abs(ComplexNumber(0, 0)) == 0


def test_square_of_abs_equals_z_times_conjugate():
    z = ComplexNumber(3, 4)
    assert_close(z * z.conjugate(), 25, 0)
    assert abs(z) ** 2 == pytest.approx(25)


def test_addition():
    assert_close(ComplexNumber(1, 2) + ComplexNumber(3, 4), 4, 6)
    assert_close(ComplexNumber(1, -2) + ComplexNumber(-1, 2), 0, 0)


def test_subtraction():
    assert_close(ComplexNumber(3, 4) - ComplexNumber(1, 2), 2, 2)
    assert_close(ComplexNumber(1, 2) - ComplexNumber(3, 4), -2, -2)


def test_multiplication():
    assert_close(ComplexNumber(1, 2) * ComplexNumber(3, 4), -5, 10)
    assert_close(ComplexNumber(0, 1) * ComplexNumber(0, 1), -1, 0)
    assert_close(ComplexNumber(2, 0) * ComplexNumber(0, 3), 0, 6)


def test_division():
    # 1 / i = -i
    assert_close(ComplexNumber(1, 0) / ComplexNumber(0, 1), 0, -1)
    # (1 + 2i) / (3 + 4i) = (11 + 2i) / 25
    assert_close(ComplexNumber(1, 2) / ComplexNumber(3, 4), 0.44, 0.08)
    # (-6 + 8i) / (2i) = 4 + 3i
    assert_close(ComplexNumber(-6, 8) / ComplexNumber(0, 2), 4, 3)


def test_exp_of_zero_is_one():
    assert_close(ComplexNumber(0, 0).exp(), 1, 0)


def test_exp_of_real_number_is_e_power():
    assert_close(ComplexNumber(1, 0).exp(), math.e, 0)
    assert_close(ComplexNumber(-1, 0).exp(), 1 / math.e, 0)


def test_exp_of_imaginary_number_is_euler_formula():
    assert_close(ComplexNumber(0, 1).exp(), math.cos(1), math.sin(1))
    assert abs(ComplexNumber(0, 1).exp()) == pytest.approx(1)


def test_exp_of_i_pi_is_minus_one():
    assert_close(ComplexNumber(0, math.pi).exp(), -1, 0)


def test_exp_of_general_complex_number():
    # e^(0 + (pi/2)i) = e * i
    assert_close(ComplexNumber(0, math.pi / 2).exp(), 0, math.e)
    # e^(1 + (pi/2)i) = e * e^(pi/2 * i) = e * i
    assert_close(ComplexNumber(1, math.pi / 2).exp(), 0, math.e)
