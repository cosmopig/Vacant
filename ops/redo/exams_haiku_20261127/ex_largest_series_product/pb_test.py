import pytest

from largest_series_product import largest_product


def test_worked_example_63915_span_3_is_162():
    """REQ: "So the answer is 162." (example input "63915", span 3; series 639, 391, 915 have products 162, 27, 45)"""
    assert largest_product("63915", 3) == 162


def test_series_are_adjacent_digits_not_pairs_of_any_digits():
    """REQ: "To form a series, take adjacent digits in the original input." ("1919" with span 2: adjacent series 19, 91, 19 each have product 9, not 81)"""
    assert largest_product("1919", 2) == 9


def test_span_2_adjacent_pairs_of_123456789_max_is_72():
    """REQ: "series: a sequence of adjacent digits (those that are next to each other) that is contained within the input" (adjacent pair products 2, 6, 12, 20, 30, 42, 56, 72; max 72)"""
    assert largest_product("123456789", 2) == 72


def test_span_3_of_123456789_max_is_504():
    """REQ: "If you are working with a span of `3`, there will be three possible series" (products 6, 24, 60, 120, 210, 336, 504; max 504)"""
    assert largest_product("123456789", 3) == 504


def test_span_equal_to_input_length_gives_product_of_whole_input():
    """REQ: "span: how many digits long each series is" (span 5 on a 5-digit input has exactly one series, the whole input: 6*3*9*1*5 = 810)"""
    assert largest_product("63915", 5) == 810


def test_span_1_gives_largest_single_digit():
    """REQ: "span: how many digits long each series is" (span 1 series are single digits; largest in "63915" is 9)"""
    assert largest_product("63915", 1) == 9


def test_single_digit_input_with_span_1_returns_that_digit():
    """REQ: "series: a sequence of adjacent digits (those that are next to each other) that is contained within the input" (only one series, "7", product 7)"""
    assert largest_product("7", 1) == 7


def test_result_is_an_integer():
    """REQ: "product: what you get when you multiply numbers together" (the largest series product is a whole number, here 162)"""
    result = largest_product("63915", 3)
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_series_containing_zero_has_product_zero():
    """REQ: "product: what you get when you multiply numbers together" ("10203" with span 2: every adjacent pair contains a 0, so every product is 0)"""
    assert largest_product("10203", 2) == 0


def test_leading_zero_series_is_included_in_search():
    """REQ: "To form a series, take adjacent digits in the original input." ("0912" with span 2: series 09=0, 91=9, 12=2; max 9)"""
    assert largest_product("0912", 2) == 9


def test_all_nines_span_5_is_9_to_the_fifth():
    """REQ: "product: what you get when you multiply numbers together" ("99999" with span 5 gives 9*9*9*9*9 = 59049)"""
    assert largest_product("99999", 5) == 59049


def test_span_longer_than_input_raises_value_error_with_message():
    """REQ: "span must not exceed string length" ("123" with span 4 must raise ValueError with a meaningful message)"""
    with pytest.raises(ValueError) as excinfo:
        largest_product("123", 4)
    assert str(excinfo.value).strip() != ""


def test_empty_input_with_positive_span_raises_value_error_with_message():
    """REQ: "span must not exceed string length" (empty input "" has length 0, so span 1 exceeds it and must raise ValueError with a message)"""
    with pytest.raises(ValueError) as excinfo:
        largest_product("", 1)
    assert str(excinfo.value).strip() != ""


def test_negative_span_raises_value_error_with_message():
    """REQ: "span must not be negative" (span -1 on "12345" must raise ValueError with a meaningful message)"""
    with pytest.raises(ValueError) as excinfo:
        largest_product("12345", -1)
    assert str(excinfo.value).strip() != ""


def test_non_digit_letter_in_input_raises_value_error_with_message():
    """REQ: "digits input must only contain digits" ("12a45" contains a letter; must raise ValueError with a message)"""
    with pytest.raises(ValueError) as excinfo:
        largest_product("12a45", 2)
    assert str(excinfo.value).strip() != ""


def test_non_digit_minus_sign_in_input_raises_value_error_with_message():
    """REQ: "digits input must only contain digits" ("1-234" contains a minus sign, which is not a digit; must raise ValueError with a message)"""
    with pytest.raises(ValueError) as excinfo:
        largest_product("1-234", 2)
    assert str(excinfo.value).strip() != ""


def test_validation_error_messages_are_not_empty_for_all_invalid_cases():
    """REQ: "The tests will only pass if you both `raise` the `exception` and include a message with it." (each invalid case must raise ValueError whose message is a non-empty string)"""
    with pytest.raises(ValueError) as excinfo:
        largest_product("12", 3)
    assert isinstance(str(excinfo.value), str)
    assert str(excinfo.value).strip() != ""
