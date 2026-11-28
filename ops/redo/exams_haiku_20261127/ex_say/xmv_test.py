import pytest

from say import say


# SRC: "0 → zero"
def test_zero():
    pass  # deleted by xmv_post: no_src


# SRC: "1 → one"
def test_one():
    pass  # deleted by xmv_post: no_src


# SRC: "12 → twelve"
def test_twelve():
    pass  # deleted by xmv_post: no_src


# SRC: "123 → one hundred twenty-three"
def test_one_hundred_twenty_three():
    pass  # deleted by xmv_post: no_src


# SRC: "123 → one hundred twenty-three"
def test_one_hundred():
    pass  # deleted by xmv_post: no_src


# SRC: "1,234 → one thousand two hundred thirty-four"
def test_one_thousand_two_hundred_thirty_four():
    pass  # deleted by xmv_post: no_src


# SRC: "1,234 → one thousand two hundred thirty-four"
def test_one_thousand():
    pass  # deleted by xmv_post: no_src


# SRC: "expects to use numbers from 0 up to 999,999,999,999."
def test_one_million():
    pass  # deleted by xmv_post: no_src


# SRC: "expects to use numbers from 0 up to 999,999,999,999."
def test_upper_bound_999_billion_999_million_999_thousand_999():
    pass  # deleted by xmv_post: no_src


# SRC: "# if the number is negative"
def test_negative_number_raises_value_error():
    pass  # deleted by xmv_post: no_src


# SRC: "# if the number is larger than 999,999,999,999"
def test_number_above_upper_bound_raises_value_error():
    pass  # deleted by xmv_post: no_src


# SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
def test_out_of_range_error_includes_message():
    pass  # deleted by xmv_post: no_src
    # SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
    assert str(excinfo.value) != ""
