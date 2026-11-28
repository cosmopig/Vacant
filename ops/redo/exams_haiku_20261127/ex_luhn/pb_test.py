"""Acceptance tests for the Luhn validation exercise.

Each check function covers one property taken from the requirements text.
Expected values were derived by hand from the Luhn rules in the text.
"""
from luhn import Luhn


def test_valid_returns_bool_type():
    """REQ: "Determine whether a number is valid according to the [Luhn formula][luhn]."

    The result of valid() must be a bool, not just a truthy or falsy value.
    """
    assert Luhn("4539 3195 0343 6467").valid() is True
    assert Luhn("066 123 478").valid() is False


def test_input_is_a_string_of_digits_and_spaces_accepted():
    """REQ: "The number will be provided as a string."

    A digit string (with spaces) is accepted by the constructor and checked.
    """
    assert Luhn("59").valid() is True
    assert Luhn("4539319503436467").valid() is True


def test_valid_credit_card_example():
    """REQ: "The number to be checked is `4539 3195 0343 6467`."

    The doubling, subtraction and summing steps give a total of 80, which is
    divisible by 10, so the number is valid.
    """
    assert Luhn("4539 3195 0343 6467").valid() is True


def test_invalid_canadian_sin_example():
    """REQ: "The number to be checked is `066 123 478`."

    The digit sum is 36, which is not divisible by 10, so the number is not valid.
    """
    assert Luhn("066 123 478").valid() is False


def test_single_digit_is_not_valid():
    """REQ: "Strings of length 1 or less are not valid."

    The string "0" has length 1 and must be rejected, even though its digit sum is 0.
    """
    assert Luhn("0").valid() is False
    assert Luhn("5").valid() is False


def test_empty_string_is_not_valid():
    """REQ: "Strings of length 1 or less are not valid."

    The empty string has length 0 and must be rejected.
    """
    assert Luhn("").valid() is False


def test_minimum_valid_length_two_can_be_valid():
    """REQ: "Strings of length 1 or less are not valid."

    Length 2 is above the stated limit, so a valid length-2 string is accepted.
    "00" has digit sum 0, which is divisible by 10.
    """
    assert Luhn("00").valid() is True


def test_spaces_are_stripped_before_checking():
    """REQ: "Spaces are allowed in the input, but they should be stripped before checking."

    The spaced and unspaced forms of the same digits give the same result.
    """
    assert Luhn("4539 3195 0343 6467").valid() is True
    assert Luhn("4539319503436467").valid() is True
    assert Luhn("0 0").valid() is True


def test_leading_and_trailing_spaces_are_stripped():
    """REQ: "Spaces are allowed in the input, but they should be stripped before checking."

    Leading and trailing spaces are removed, so "  59  " is checked as "59".
    """
    assert Luhn("  59  ").valid() is True


def test_whitespace_only_input_is_not_valid():
    """REQ: "Strings of length 1 or less are not valid."

    After spaces are stripped, the string is empty and so is not valid.
    """
    assert Luhn("    ").valid() is False


def test_single_digit_with_trailing_space_is_not_valid():
    """REQ: "Strings of length 1 or less are not valid."

    After stripping, "0 " has length 1 and must be rejected.
    """
    assert Luhn("0 ").valid() is False


def test_letters_are_disallowed():
    """REQ: "All other non-digit characters are disallowed."

    A letter anywhere in the input makes the number not valid.
    """
    assert Luhn("4539 3195 0343 646a").valid() is False
    assert Luhn("a1").valid() is False


def test_punctuation_is_disallowed():
    """REQ: "All other non-digit characters are disallowed."

    Non-digit, non-space characters such as "-" make the number not valid.
    """
    assert Luhn("5-9").valid() is False
    assert Luhn("59-").valid() is False


def test_doubled_digit_above_nine_has_nine_subtracted():
    """REQ: "If the result of doubling a digit is greater than 9, we subtract 9 from that result."

    For "59", doubling 5 gives 10, minus 9 gives 1. The sum is 1 + 9 = 10, so it is valid.
    For "91", doubling 9 gives 18, minus 9 gives 9. The sum is 9 + 1 = 10, so it is valid.
    """
    assert Luhn("59").valid() is True
    assert Luhn("91").valid() is True


def test_rightmost_digit_is_not_doubled():
    """REQ: "start at the end of the number and double every second digit, beginning with the second digit from the right and moving left."

    For "19", only the left digit 1 is doubled, giving 2. The sum is 2 + 9 = 11,
    so it is not valid. If the rightmost digit were doubled, the sum would be 10.
    """
    assert Luhn("19").valid() is False


def test_changing_check_digit_of_valid_number_makes_it_invalid():
    """REQ: "If the sum is evenly divisible by 10, the original number is valid."

    The rightmost digit is not doubled, so changing 7 to 8 raises the sum from
    80 to 81, which is not divisible by 10.
    """
    assert Luhn("4539 3195 0343 6467").valid() is True
    assert Luhn("4539 3195 0343 6468").valid() is False


def test_validation_is_deterministic_across_calls():
    """REQ: "Determine whether a number is valid according to the [Luhn formula][luhn]."

    Repeated checks of the same input give the same result, whether on one
    instance or on separate instances.
    """
    first = Luhn("4539 3195 0343 6467")
    assert first.valid() is True
    assert first.valid() is True
    assert Luhn("4539 3195 0343 6467").valid() is True
    assert Luhn("066 123 478").valid() is False
    assert Luhn("066 123 478").valid() is False
