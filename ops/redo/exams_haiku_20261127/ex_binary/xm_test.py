import pytest

from binary import parse_binary


def test_zero():
    assert parse_binary("0") == 0


def test_one():
    assert parse_binary("1") == 1


def test_two_digit_binary():
    assert parse_binary("10") == 2


def test_example_from_requirements():
    assert parse_binary("101") == 5


def test_longer_example_from_requirements():
    assert parse_binary("101010") == 42


def test_all_ones_byte():
    assert parse_binary("11111111") == 255


def test_power_of_two():
    assert parse_binary("10000000000") == 1024


def test_leading_zeros_do_not_change_value():
    assert parse_binary("0001") == 1
    assert parse_binary("000101") == 5


def test_long_input_all_ones():
    assert parse_binary("1" * 64) == 2**64 - 1


def test_invalid_digit_two_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        parse_binary("2")
    assert len(str(excinfo.value).strip()) > 0


def test_invalid_digit_inside_string_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        parse_binary("102")
    assert len(str(excinfo.value).strip()) > 0


def test_non_numeric_characters_raise_value_error():
    with pytest.raises(ValueError) as excinfo:
        parse_binary("abc")
    assert len(str(excinfo.value).strip()) > 0


def test_mixed_valid_and_invalid_characters_raise_value_error():
    with pytest.raises(ValueError) as excinfo:
        parse_binary("1a0")
    assert len(str(excinfo.value).strip()) > 0
