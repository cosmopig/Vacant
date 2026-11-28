import pytest

from say import say


# SRC: "0 → zero"
def test_zero():
    assert say(0) == "zero"


# SRC: "1 → one"
def test_one():
    assert say(1) == "one"


# SRC: "12 → twelve"
def test_twelve():
    assert say(12) == "twelve"


# SRC: "123 → one hundred twenty-three"
def test_one_hundred_twenty_three():
    assert say(123) == "one hundred twenty-three"


# SRC: "123 → one hundred twenty-three"
def test_one_hundred():
    assert say(100) == "one hundred"


# SRC: "1,234 → one thousand two hundred thirty-four"
def test_one_thousand_two_hundred_thirty_four():
    assert say(1234) == "one thousand two hundred thirty-four"


# SRC: "1,234 → one thousand two hundred thirty-four"
def test_one_thousand():
    assert say(1000) == "one thousand"


# SRC: "expects to use numbers from 0 up to 999,999,999,999."
def test_one_million():
    assert say(1000000) == "one million"


# SRC: "expects to use numbers from 0 up to 999,999,999,999."
def test_upper_bound_999_billion_999_million_999_thousand_999():
    assert say(999999999999) == (
        "nine hundred ninety-nine billion nine hundred ninety-nine million "
        "nine hundred ninety-nine thousand nine hundred ninety-nine"
    )


# SRC: "# if the number is negative"
def test_negative_number_raises_value_error():
    with pytest.raises(ValueError):
        say(-1)


# SRC: "# if the number is larger than 999,999,999,999"
def test_number_above_upper_bound_raises_value_error():
    with pytest.raises(ValueError):
        say(1000000000000)


# SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
def test_out_of_range_error_includes_message():
    with pytest.raises(ValueError) as excinfo:
        say(-1)
    # SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
    assert str(excinfo.value) != ""
