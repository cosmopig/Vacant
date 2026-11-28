from luhn import Luhn


def test_valid_credit_card_example():
    # Worked example from the requirements: sums to 80.
    assert Luhn("4539 3195 0343 6467").valid()


def test_invalid_canadian_sin_example():
    # Worked example from the requirements: sums to 36.
    assert not Luhn("066 123 478").valid()


def test_valid_three_digit_number():
    # Doubled 5 -> 10 -> 1; sum 0 + 1 + 9 = 10.
    assert Luhn("059").valid()


def test_invalid_single_digit_change():
    # Doubled 6 -> 12 -> 3; sum 0 + 3 + 9 = 12.
    assert not Luhn("069").valid()


def test_two_digit_valid_number():
    # Doubled 5 -> 10 -> 1; sum 9 + 1 = 10.
    assert Luhn("59").valid()


def test_two_digit_invalid_number():
    # Doubled 1 -> 2; sum 9 + 2 = 11.
    assert not Luhn("19").valid()


def test_two_zeros_are_valid_length_boundary():
    # Length 2 is allowed; sum 0 is divisible by 10.
    assert Luhn("00").valid()


def test_spaces_are_stripped_before_length_check():
    # "0 0" becomes "00" (length 2), which is valid.
    assert Luhn("0 0").valid()


def test_single_digit_is_invalid():
    # Strings of length 1 or less are not valid.
    assert not Luhn("0").valid()


def test_single_digit_with_surrounding_spaces_is_invalid():
    # Stripped to "0", which has length 1.
    assert not Luhn(" 0 ").valid()


def test_empty_string_is_invalid():
    assert not Luhn("").valid()


def test_only_spaces_is_invalid():
    # Stripped to an empty string.
    assert not Luhn("   ").valid()


def test_multiple_internal_spaces_are_ignored():
    # Same digits as the credit card example, with extra spaces.
    assert Luhn("4539  3195   0343 6467").valid()


def test_letter_is_disallowed():
    assert not Luhn("4539a3195").valid()


def test_hyphen_is_disallowed():
    assert not Luhn("4539-3195").valid()
