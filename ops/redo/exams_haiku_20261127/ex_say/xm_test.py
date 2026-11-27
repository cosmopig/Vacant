import pytest

from say import say


def test_zero():
    assert say(0) == "zero"


def test_single_digits():
    assert say(1) == "one"


def test_teens_and_tens():
    assert say(12) == "twelve"
    assert say(20) == "twenty"


def test_hundreds():
    assert say(100) == "one hundred"
    assert say(123) == "one hundred twenty-three"


def test_thousands():
    assert say(1000) == "one thousand"
    assert say(1234) == "one thousand two hundred thirty-four"


def test_gap_in_scale_group_is_not_spoken():
    assert say(1002) == "one thousand two"


def test_hundred_thousands():
    assert say(100000) == "one hundred thousand"


def test_millions():
    assert say(1000000) == "one million"


def test_billions():
    assert say(1000000000) == "one billion"


def test_largest_allowed_number():
    assert say(999999999999) == (
        "nine hundred ninety-nine billion "
        "nine hundred ninety-nine million "
        "nine hundred ninety-nine thousand "
        "nine hundred ninety-nine"
    )


def test_negative_number_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        say(-1)
    assert str(excinfo.value) != ""


def test_number_above_range_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        say(1000000000000)
    assert str(excinfo.value) != ""
