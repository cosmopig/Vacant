import pytest

from all_your_base import rebase


def test_binary_to_decimal():
    # SRC: "The number 101010, _in base 2_, means:"
    assert rebase(2, [1, 0, 1, 0, 1, 0], 10) == [4, 2]


def test_decimal_to_binary():
    # SRC: "The number 42, _in base 10_, means:"
    assert rebase(10, [4, 2], 2) == [1, 0, 1, 0, 1, 0]


def test_base3_to_decimal():
    # SRC: "The number 1120, _in base 3_, means:"
    assert rebase(3, [1, 1, 2, 0], 10) == [4, 2]


def test_decimal_to_base3():
    # SRC: "Those three numbers above are exactly the same."
    assert rebase(10, [4, 2], 3) == [1, 1, 2, 0]


def test_output_base_above_ten_uses_integer_digits():
    # SRC: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."
    assert rebase(10, [4, 2], 16) == [2, 10]


def test_input_base_above_ten_uses_integer_digits():
    # SRC: "all digits must satisfy 0 <= d < input base"
    assert rebase(16, [2, 10], 10) == [4, 2]


def test_single_digit():
    # SRC: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."
    assert rebase(2, [1], 10) == [1]


def test_leading_zeros_do_not_change_value():
    # SRC: "In positional notation, a number in base **b** can be understood as a linear combination of powers of **b**."
    assert rebase(2, [0, 0, 1, 0, 1, 0, 1, 0], 10) == [4, 2]


def test_input_base_below_two_raises_value_error():
    # SRC: `raise ValueError("input base must be >= 2")`
    pass  # deleted by xmv_post: no_src


def test_output_base_below_two_raises_value_error():
    # SRC: `raise ValueError("output base must be >= 2")`
    pass  # deleted by xmv_post: no_src


def test_digit_equal_to_input_base_raises_value_error():
    # SRC: `raise ValueError("all digits must satisfy 0 <= d < input base")`
    pass  # deleted by xmv_post: no_src


def test_negative_digit_raises_value_error():
    # SRC: `raise ValueError("all digits must satisfy 0 <= d < input base")`
    pass  # deleted by xmv_post: no_src


def test_value_error_includes_meaningful_message():
    # SRC: "include a **meaningful error message**"
    with pytest.raises(ValueError) as excinfo:
        rebase(2, [2], 10)
    # SRC: "include a **meaningful error message**"
    assert str(excinfo.value).strip() != ""
