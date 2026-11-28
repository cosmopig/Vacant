import pytest

from series import slices


def test_three_digit_slices_of_49142():
    assert slices("49142", 3) == ["491", "914", "142"]


def test_four_digit_slices_of_49142():
    assert slices("49142", 4) == ["4914", "9142"]


def test_one_digit_slices_return_each_digit_in_order():
    assert slices("49142", 1) == ["4", "9", "1", "4", "2"]


def test_slice_length_equal_to_series_length_returns_whole_series():
    assert slices("49142", 5) == ["49142"]


def test_two_digit_slices_of_single_pair_series():
    assert slices("12", 2) == ["12"]


def test_slices_need_not_be_numerically_consecutive():
    assert slices("0123", 2) == ["01", "12", "23"]


def test_repeated_digits_are_each_returned_as_a_slice():
    assert slices("1111", 2) == ["11", "11", "11"]


def test_zero_slice_length_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        slices("123", 0)
    assert str(excinfo.value) != ""


def test_negative_slice_length_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        slices("123", -1)
    assert str(excinfo.value) != ""


def test_empty_series_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        slices("", 1)
    assert str(excinfo.value) != ""


def test_slice_length_greater_than_series_length_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        slices("49142", 6)
    assert str(excinfo.value) != ""
