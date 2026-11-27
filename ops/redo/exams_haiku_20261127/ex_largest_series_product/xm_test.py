import pytest

from largest_series_product import largest_product


def test_largest_product_of_two_digit_span_in_example():
    # Pairs of adjacent digits in "63915": 18, 27, 9, 5 -> largest is 27
    assert largest_product("63915", 2) == 27


def test_largest_product_of_three_digit_span_in_example():
    # Series "639" = 6*3*9 = 162 is the largest of 162, 27, 45
    assert largest_product("63915", 3) == 162


def test_span_of_one_returns_largest_digit():
    # Single-digit series are the digits themselves; largest is 9
    assert largest_product("63915", 1) == 9


def test_span_equal_to_length_returns_product_of_all_digits():
    # Only one series exists: 6*3*9*1*5 = 810
    assert largest_product("63915", 5) == 810


def test_adjacent_pairs_across_all_digits():
    # Adjacent products: 0, 2, 6, 12, 20, 30, 42, 56, 72 -> largest is 72
    assert largest_product("0123456789", 2) == 72


def test_zeros_in_input_are_handled():
    # Adjacent products: 0, 0, 14, 56, 24, 27 -> largest is 56
    assert largest_product("1027839", 2) == 56


def test_all_zero_input_gives_zero():
    assert largest_product("0000", 2) == 0


def test_single_digit_input_with_span_one():
    assert largest_product("7", 1) == 7


def test_negative_span_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        largest_product("123", -1)
    assert str(excinfo.value)


def test_span_longer_than_input_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        largest_product("123", 4)
    assert str(excinfo.value)


def test_empty_input_with_positive_span_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        largest_product("", 1)
    assert str(excinfo.value)


def test_non_digit_input_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        largest_product("12a4", 2)
    assert str(excinfo.value)
