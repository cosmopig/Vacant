"""Acceptance tests for the all_your_base exercise (rebase)."""

from all_your_base import rebase


def test_output_is_list_of_ints():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    The result is a sequence of digits, which is represented as a list of ints.
    """
    result = rebase(10, [4, 2], 2)
    assert isinstance(result, list), f"expected a list, got {type(result).__name__}"
    for d in result:
        assert isinstance(d, int), f"digit {d!r} is not an int"


def test_output_digits_within_output_base():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    Every output digit must be a valid digit in the output base: 0 <= d < output base.
    """
    result = rebase(10, [1, 2, 3], 16)
    for d in result:
        assert 0 <= d < 16, f"digit {d} is not valid in base 16"


def test_example_binary_to_decimal():
    """REQ: "The number 101010, _in base 2_, means: (1 × 2⁵) + (0 × 2⁴) + (1 × 2³) + (0 × 2²) + (1 × 2¹) + (0 × 2⁰)"

    101010 in base 2 is 42, which is [4, 2] in base 10.
    """
    assert rebase(2, [1, 0, 1, 0, 1, 0], 10) == [4, 2]


def test_example_decimal_to_binary():
    """REQ: "The number 42, _in base 10_, means: (4 × 10¹) + (2 × 10⁰)"

    42 in base 10 is 101010 in base 2.
    """
    assert rebase(10, [4, 2], 2) == [1, 0, 1, 0, 1, 0]


def test_example_trinary_to_hexadecimal():
    """REQ: "The number 1120, _in base 3_, means: (1 × 3³) + (1 × 3²) + (2 × 3¹) + (0 × 3⁰)"

    1120 in base 3 is 42, which is [2, 10] in base 16 (2 * 16 + 10).
    """
    assert rebase(3, [1, 1, 2, 0], 16) == [2, 10]


def test_example_hexadecimal_to_trinary():
    """REQ: "Those three numbers above are exactly the same. Congratulations!"

    [2, 10] in base 16 is 42, which is 1120 in base 3.
    """
    assert rebase(16, [2, 10], 3) == [1, 1, 2, 0]


def test_zero_is_single_zero_digit():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    The number zero is represented by a single digit 0.
    """
    assert rebase(10, [0], 2) == [0]


def test_leading_zeros_in_input_do_not_change_value():
    """REQ: "In positional notation, a number in base **b** can be understood as a linear combination of powers of **b**."

    Leading zeros add nothing to the linear combination, so [0, 0, 1, 0, 1, 0, 1, 0] in base 2 is 42, which is [4, 2] in base 10.
    """
    assert rebase(2, [0, 0, 1, 0, 1, 0, 1, 0], 10) == [4, 2]


def test_no_leading_zeros_in_output():
    """REQ: "The number 42, _in base 10_, means: (4 × 10¹) + (2 × 10⁰)"

    The representation of a number has no leading zeros: 100 in base 10 is 1100100 in base 2, not 01100100.
    """
    result = rebase(10, [1, 0, 0], 2)
    assert result == [1, 1, 0, 0, 1, 0, 0], f"got {result}"
    assert result[0] != 0, "output must not start with a leading zero"


def test_single_digit_input():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    A single-digit input converts correctly: 1 in base 2 is 1 in base 10, and 9 in base 10 is 1001 in base 2.
    """
    assert rebase(2, [1], 10) == [1]
    assert rebase(10, [9], 2) == [1, 0, 0, 1]


def test_maximum_input_digit_accepted():
    """REQ: "all digits must satisfy 0 <= d < input base"

    The largest allowed digit for a base, input base minus one, is valid: 22 in base 3 is 8 in base 10.
    """
    assert rebase(3, [2, 2], 10) == [8]


def test_minimum_bases_accepted():
    """REQ: "input base must be >= 2" and "output base must be >= 2"

    Base 2 is the smallest valid input and output base, so it must be accepted for both.
    """
    assert rebase(2, [1, 1], 2) == [1, 1]


def test_same_input_and_output_base_is_identity():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    Converting from base 2 to base 2 yields the same number, so the same digits.
    """
    assert rebase(2, [1, 0, 1, 0, 1, 0], 2) == [1, 0, 1, 0, 1, 0]


def test_large_output_base_16():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    123 in base 10 is 7 * 16 + 11, so it is [7, 11] in base 16.
    """
    assert rebase(10, [1, 2, 3], 16) == [7, 11]


def test_round_trip_preserves_value():
    """REQ: "Convert a sequence of digits in one base, representing a number, into a sequence of digits in another base, representing the same number."

    Converting a number to another base and back gives the original digits.
    """
    there = rebase(10, [4, 2], 2)
    assert rebase(2, there, 10) == [4, 2]
    there16 = rebase(3, [1, 1, 2, 0], 16)
    assert rebase(16, there16, 3) == [1, 1, 2, 0]


def test_input_base_below_two_raises_value_error():
    """REQ: "input base must be >= 2" and "This particular exercise requires that you use the raise statement to 'throw' a `ValueError` for different input and output bases."

    An input base less than 2 must raise ValueError.
    """
    for bad_base in (1, 0, -2):
        try:
            rebase(bad_base, [0], 10)
        except ValueError:
            pass
        else:
            assert False, f"input base {bad_base} did not raise ValueError"


def test_output_base_below_two_raises_value_error():
    """REQ: "output base must be >= 2" and "This particular exercise requires that you use the raise statement to 'throw' a `ValueError` for different input and output bases."

    An output base less than 2 must raise ValueError.
    """
    for bad_base in (1, 0, -2):
        try:
            rebase(2, [1, 0], bad_base)
        except ValueError:
            pass
        else:
            assert False, f"output base {bad_base} did not raise ValueError"


def test_digit_not_less_than_input_base_raises_value_error():
    """REQ: "all digits must satisfy 0 <= d < input base"

    A digit equal to or greater than the input base must raise ValueError.
    """
    try:
        rebase(2, [1, 2], 10)
    except ValueError:
        pass
    else:
        assert False, "digit 2 in base 2 did not raise ValueError"
    try:
        rebase(10, [10], 2)
    except ValueError:
        pass
    else:
        assert False, "digit 10 in base 10 did not raise ValueError"


def test_negative_digit_raises_value_error():
    """REQ: "all digits must satisfy 0 <= d < input base"

    A negative digit violates 0 <= d and must raise ValueError.
    """
    try:
        rebase(10, [-1], 2)
    except ValueError:
        pass
    else:
        assert False, "negative digit did not raise ValueError"


def test_error_has_meaningful_message():
    """REQ: "When you do this, you should always include a **meaningful error message** to indicate what the source of the error is."

    The ValueError raised for an invalid base must carry a non-empty message.
    """
    try:
        rebase(1, [0], 10)
    except ValueError as exc:
        message = str(exc).strip()
        assert message, "ValueError was raised without a message"
    else:
        assert False, "input base 1 did not raise ValueError"
