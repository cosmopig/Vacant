import pytest

from binary import parse_binary


def test_worked_example_from_instructions():
    # SRC: "Convert a binary number, represented as a string (e.g. '101010'), to its decimal equivalent using first principles."
    assert parse_binary("101010") == 42


def test_worked_expansion_101_is_5():
    # SRC: "101 => 1*2^2 + 0*2^1 + 1*2^0 => 1*4 + 0*2 + 1*1 => 4 + 1 => 5 base 10"
    assert parse_binary("101") == 5


def test_zero_boundary():
    # SRC: "Given a binary input string, your program should produce a decimal output."
    assert parse_binary("0") == 0


def test_one_boundary():
    # SRC: "Binary is similar, but uses powers of 2 rather than powers of 10."
    assert parse_binary("1") == 1


def test_single_power_of_two_position():
    # SRC: "Binary is similar, but uses powers of 2 rather than powers of 10."
    assert parse_binary("10000000000") == 1024


def test_all_ones_byte():
    # SRC: "Binary is similar, but uses powers of 2 rather than powers of 10."
    assert parse_binary("11111111") == 255


def test_leading_zeros_contribute_nothing():
    # SRC: "101 => 1*2^2 + 0*2^1 + 1*2^0 => 1*4 + 0*2 + 1*1 => 4 + 1 => 5 base 10"
    assert parse_binary("000101") == 5


def test_invalid_digit_2_raises_value_error_with_message():
    # SRC: "The program should handle invalid inputs."
    with pytest.raises(ValueError) as excinfo:
        parse_binary("2")
    # SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
    assert str(excinfo.value).strip() != ""


def test_invalid_mixed_digits_raises_value_error_with_message():
    # SRC: "The program should handle invalid inputs."
    with pytest.raises(ValueError) as excinfo:
        parse_binary("102")
    # SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
    assert str(excinfo.value).strip() != ""


def test_invalid_letters_raises_value_error_with_message():
    # SRC: "The program should handle invalid inputs."
    with pytest.raises(ValueError) as excinfo:
        parse_binary("abc")
    # SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
    assert str(excinfo.value).strip() != ""
