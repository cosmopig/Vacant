import pytest

from largest_series_product import largest_product


def test_worked_example_span_three():
    # SRC: "Let's work through an example, with the input"
    assert largest_product("63915", 3) == 162


def test_span_two_on_worked_example():
    # SRC: "how many digits long each series is"
    assert largest_product("63915", 2) == 27


def test_span_one_returns_largest_digit():
    # SRC: "how many digits long each series is"
    assert largest_product("63915", 1) == 9


def test_span_equal_to_length_uses_whole_input():
    # SRC: "a sequence of adjacent digits (those that are next to each other) that is contained within the input"
    assert largest_product("12345", 5) == 120


def test_span_equal_to_length_two_digits():
    # SRC: "To form a series, take adjacent digits in the original input."
    assert largest_product("29", 2) == 18


def test_span_equal_to_length_three_digits():
    # SRC: "how many digits long each series is"
    assert largest_product("123", 3) == 6


def test_series_are_adjacent_digits_only():
    # SRC: "To form a series, take adjacent digits in the original input."
    assert largest_product("123456789", 3) == 504


def test_zero_digit_in_series_gives_product_zero_when_it_is_max():
    # SRC: "what you get when you multiply numbers together"
    assert largest_product("0000", 2) == 0


def test_series_containing_zero_is_not_chosen_when_others_larger():
    # SRC: "what you get when you multiply numbers together"
    assert largest_product("0123", 2) == 6


def test_all_nines_product():
    # SRC: "what you get when you multiply numbers together"
    assert largest_product("99999", 5) == 59049


def test_span_longer_than_input_raises_value_error():
    # SRC: "span of numbers is longer than number series"
    with pytest.raises(ValueError):
        largest_product("123", 4)


def test_span_longer_than_input_error_has_message():
    # SRC: "include a message with it"
    with pytest.raises(ValueError) as excinfo:
        largest_product("123", 4)
    # SRC: "include a message with it"
    assert str(excinfo.value) != ""


def test_span_longer_than_empty_input_raises_value_error():
    # SRC: "span of numbers is longer than number series"
    with pytest.raises(ValueError):
        largest_product("", 1)


def test_negative_span_raises_value_error():
    # SRC: "span of number is negative"
    with pytest.raises(ValueError):
        largest_product("123", -1)


def test_negative_span_error_has_message():
    # SRC: "include a message with it"
    with pytest.raises(ValueError) as excinfo:
        largest_product("123", -1)
    # SRC: "include a message with it"
    assert str(excinfo.value) != ""


def test_non_digit_input_raises_value_error():
    # SRC: "series includes non-number input"
    with pytest.raises(ValueError):
        largest_product("12a4", 2)


def test_non_digit_input_error_has_message():
    # SRC: "include a message with it"
    with pytest.raises(ValueError) as excinfo:
        largest_product("12a4", 2)
    # SRC: "include a message with it"
    assert str(excinfo.value) != ""
