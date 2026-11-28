"""Acceptance tests for binary.parse_binary (binary string -> decimal int)."""

import pytest

from binary import parse_binary


def test_returns_int_for_string_input():
    """REQ: "Given a binary input string, your program should produce a decimal output." """
    result = parse_binary("101010")
    assert isinstance(result, int)
    assert not isinstance(result, bool)


def test_example_101010_is_42():
    """REQ: "Convert a binary number, represented as a string (e.g. '101010'), to its decimal equivalent using first principles." """
    assert parse_binary("101010") == 42


def test_example_101_is_5():
    """REQ: "So: `101 => 1*2^2 + 0*2^1 + 1*2^0 => 1*4 + 0*2 + 1*1 => 4 + 1 => 5 base 10`." """
    assert parse_binary("101") == 5


def test_zero_and_one_boundaries():
    """REQ: "The rightmost digit gets multiplied by 10^0 = 1" (single-digit binary strings '0' and '1' map to 0 and 1)."""
    assert parse_binary("0") == 0
    assert parse_binary("1") == 1


def test_all_ones_equals_power_of_two_minus_one():
    """REQ: "Binary is similar, but uses powers of 2 rather than powers of 10." (a run of n ones is 2^n - 1)."""
    assert parse_binary("1") == 2**1 - 1
    assert parse_binary("11") == 2**2 - 1
    assert parse_binary("111") == 2**3 - 1
    assert parse_binary("11111111") == 2**8 - 1


def test_single_one_followed_by_zeros_is_power_of_two():
    """REQ: "The *n*th number gets multiplied by 10^*(n-1)*." (applied to base 2: a 1 in position n contributes 2^(n-1))."""
    for k in range(0, 12):
        binary = "1" + "0" * k
        assert parse_binary(binary) == 2**k, f"failed for {binary!r}"


def test_leading_zeros_do_not_change_value():
    """REQ: "All these values are summed." (leading zeros contribute 0 * 2^n terms and so do not change the sum)."""
    assert parse_binary("0001") == 1
    assert parse_binary("00101010") == 42
    assert parse_binary("0000") == 0


def test_appending_zero_doubles_value():
    """REQ: "Binary is similar, but uses powers of 2 rather than powers of 10." (appending a digit 0 shifts all place values up by one power of 2)."""
    for s in ["1", "10", "101", "101010", "11111"]:
        assert parse_binary(s + "0") == 2 * parse_binary(s), f"failed for {s!r}"


def test_appending_one_doubles_and_adds_one():
    """REQ: "So: `23 => 2*10^1 + 3*10^0 => 2*10 + 3*1 = 23 base 10`" (the same positional rule applied to base 2 gives 2*value + digit when a digit is appended)."""
    for s in ["0", "1", "10", "101", "101010"]:
        assert parse_binary(s + "1") == 2 * parse_binary(s) + 1, f"failed for {s!r}"


def test_long_input_is_exact():
    """REQ: "Given a binary input string, your program should produce a decimal output." (output must be exact for long inputs)."""
    assert parse_binary("1" * 64) == 2**64 - 1
    assert parse_binary("1" + "0" * 100) == 2**100


@pytest.mark.parametrize("bad", ["2", "12", "1a", "10z1", "9"])
def test_rejects_digits_other_than_0_and_1(bad):
    """REQ: "The program should handle invalid inputs." (a digit other than 0 or 1 is not a valid binary literal)."""
    with pytest.raises(ValueError):
        parse_binary(bad)


@pytest.mark.parametrize("bad", ["abc", "1.0", "hello", "1,0", "0x1F"])
def test_rejects_non_digit_characters(bad):
    """REQ: "This particular exercise requires that you use the raise statement to 'throw' a `ValueError` when the argument passed is not a valid binary literal." """
    with pytest.raises(ValueError):
        parse_binary(bad)


@pytest.mark.parametrize("bad", ["-1", "-101", "+101"])
def test_rejects_sign_characters(bad):
    """REQ: "The program should handle invalid inputs." (signed strings are not binary literals in this exercise's format)."""
    with pytest.raises(ValueError):
        parse_binary(bad)


@pytest.mark.parametrize("bad", ["1 0", " 101", "101 ", "1\t0", "\n1"])
def test_rejects_whitespace(bad):
    """REQ: "The program should handle invalid inputs." (embedded or surrounding whitespace is not part of a binary literal)."""
    with pytest.raises(ValueError):
        parse_binary(bad)


def test_rejects_empty_string():
    """REQ: "This particular exercise requires that you use the raise statement to 'throw' a `ValueError` when the argument passed is not a valid binary literal." (an empty string has no digits and is not a binary literal)."""
    with pytest.raises(ValueError):
        parse_binary("")


@pytest.mark.parametrize("bad", ["2", "abc", "101a", ""])
def test_error_carries_nonempty_message(bad):
    """REQ: "When you do this, you should always include a **meaningful error message** to indicate what the source of the error is." """
    with pytest.raises(ValueError) as excinfo:
        parse_binary(bad)
    message = str(excinfo.value)
    assert isinstance(message, str)
    assert message.strip() != ""
