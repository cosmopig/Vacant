import pytest

from all_your_base import rebase


def _assert_value_error_with_message(*args):
    with pytest.raises(ValueError) as excinfo:
        rebase(*args)
    assert str(excinfo.value).strip(), "ValueError must carry a meaningful message"


def test_decimal_42_to_binary():
    # 42 = (1*2^5) + (0*2^4) + (1*2^3) + (0*2^2) + (1*2^1) + (0*2^0)
    assert rebase(10, [4, 2], 2) == [1, 0, 1, 0, 1, 0]


def test_binary_to_decimal():
    assert rebase(2, [1, 0, 1, 0, 1, 0], 10) == [4, 2]


def test_base_3_to_decimal():
    # 1120 in base 3 = 1*27 + 1*9 + 2*3 + 0 = 42
    assert rebase(3, [1, 1, 2, 0], 10) == [4, 2]


def test_decimal_to_base_3():
    # 42 = 1*27 + 1*9 + 2*3 + 0*1 -> 1120
    assert rebase(10, [4, 2], 3) == [1, 1, 2, 0]


def test_zero_is_single_digit_zero():
    assert rebase(10, [0], 2) == [0]


def test_leading_zeros_in_input_are_ignored():
    # 000 in base 2 is zero.
    assert rebase(2, [0, 0, 0], 10) == [0]


def test_digits_above_nine_in_output():
    # 255 = 15*16 + 15
    assert rebase(10, [2, 5, 5], 16) == [15, 15]


def test_digits_above_nine_in_input():
    # 15*16 + 15 = 255 = 11111111 in base 2
    assert rebase(16, [15, 15], 2) == [1, 1, 1, 1, 1, 1, 1, 1]


def test_larger_number_to_binary():
    # 100 = 64 + 32 + 4
    assert rebase(10, [1, 0, 0], 2) == [1, 1, 0, 0, 1, 0, 0]


def test_single_digit_one_round_trip():
    assert rebase(2, [1], 10) == [1]
    assert rebase(10, [1], 2) == [1]


def test_input_base_must_be_at_least_two():
    _assert_value_error_with_message(1, [1], 10)
    _assert_value_error_with_message(0, [0], 10)


def test_output_base_must_be_at_least_two():
    _assert_value_error_with_message(10, [1], 1)
    _assert_value_error_with_message(10, [1], 0)


def test_digit_must_be_less_than_input_base():
    _assert_value_error_with_message(2, [2], 10)
    _assert_value_error_with_message(10, [10], 2)


def test_digit_must_not_be_negative():
    _assert_value_error_with_message(10, [-1], 2)
