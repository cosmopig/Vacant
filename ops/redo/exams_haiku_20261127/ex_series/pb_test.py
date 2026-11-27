import pytest

from series import slices


def test_returns_list_of_strings():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."

    The output is a list whose items are all strings.
    """
    result = slices("49142", 3)
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, str)


def test_each_item_has_requested_length():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."

    Every item in the output has exactly the requested number of digits.
    """
    result = slices("1234567", 3)
    assert len(result) > 0
    for item in result:
        assert len(item) == 3


def test_three_digit_example_from_text():
    """REQ: "For example, the string '49142' has the following 3-digit series: '491', '914', '142'."

    The 3-digit series of "49142" is exactly ["491", "914", "142"].
    """
    assert slices("49142", 3) == ["491", "914", "142"]


def test_four_digit_example_from_text():
    """REQ: "And the following 4-digit series: '4914', '9142'."

    The 4-digit series of "49142" is exactly ["4914", "9142"].
    """
    assert slices("49142", 4) == ["4914", "9142"]


def test_number_of_items_is_length_minus_n_plus_one():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string."

    A string of 7 digits has 7 - 3 + 1 = 5 contiguous substrings of length 3.
    """
    assert len(slices("1234567", 3)) == 5


def test_substrings_appear_in_positional_order():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."

    The substrings of "1234567" with length 3 come out from left to right.
    """
    assert slices("1234567", 3) == ["123", "234", "345", "456", "567"]


def test_repeated_substrings_are_all_kept():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."

    Identical substrings at different positions are each output, not removed as duplicates.
    """
    assert slices("0000", 2) == ["00", "00", "00"]


def test_digits_need_not_be_numerically_consecutive():
    """REQ: "Note that these series are only required to occupy adjacent positions in the input; the digits need not be numerically consecutive."

    Substrings are taken from adjacent positions even when the digits are not consecutive numbers.
    """
    assert slices("1357", 2) == ["13", "35", "57"]


def test_length_one_gives_each_digit_in_order():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."

    With length 1, each digit of the series is returned as its own item, in order.
    """
    assert slices("49142", 1) == ["4", "9", "1", "4", "2"]


def test_length_equal_to_series_length_gives_whole_series():
    """REQ: "This particular exercise requires that you use the raise statement to 'throw' a ValueError if the series and/or length parameters input into the slice() function are empty or out of range."

    A length equal to the series length is in range, and the only substring is the whole series.
    """
    assert slices("49142", 5) == ["49142"]


def test_single_digit_series_with_length_one():
    """REQ: "Given a string of digits, output all the contiguous substrings of length `n` in that string in the order that they appear."

    A one-digit series with length 1 yields that single digit.
    """
    assert slices("7", 1) == ["7"]


def test_empty_series_raises_value_error_with_message():
    """REQ: "This particular exercise requires that you use the raise statement to 'throw' a ValueError if the series and/or length parameters input into the slice() function are empty or out of range."

    An empty series raises ValueError, and the exception carries a non-empty message.
    """
    with pytest.raises(ValueError) as excinfo:
        slices("", 1)
    assert str(excinfo.value).strip() != ""


def test_zero_length_raises_value_error_with_message():
    """REQ: "This particular exercise requires that you use the raise statement to 'throw' a ValueError if the series and/or length parameters input into the slice() function are empty or out of range."

    A slice length of zero raises ValueError, and the exception carries a non-empty message.
    """
    with pytest.raises(ValueError) as excinfo:
        slices("49142", 0)
    assert str(excinfo.value).strip() != ""


def test_negative_length_raises_value_error_with_message():
    """REQ: "This particular exercise requires that you use the raise statement to 'throw' a ValueError if the series and/or length parameters input into the slice() function are empty or out of range."

    A negative slice length raises ValueError, and the exception carries a non-empty message.
    """
    with pytest.raises(ValueError) as excinfo:
        slices("49142", -1)
    assert str(excinfo.value).strip() != ""


def test_length_longer_than_series_raises_value_error_with_message():
    """REQ: "And if you ask for a 6-digit series from a 5-digit string, you deserve whatever you get."

    A slice length greater than the series length is out of range, so it raises ValueError with a non-empty message.
    """
    with pytest.raises(ValueError) as excinfo:
        slices("123", 4)
    assert str(excinfo.value).strip() != ""
