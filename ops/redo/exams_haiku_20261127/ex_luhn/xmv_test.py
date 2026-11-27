import pytest

from luhn import Luhn


# SRC: "80 is evenly divisible by 10, so number `4539 3195 0343 6467` is valid!"
def test_valid_credit_card_number_with_spaces():
    pass  # deleted by xmv_post: no_src


# SRC: "36 is not evenly divisible by 10, so number `066 123 478` is not valid!"
def test_invalid_canadian_sin():
    pass  # deleted by xmv_post: no_src


# SRC: "Strings of length 1 or less are not valid."
def test_single_digit_is_invalid():
    pass  # deleted by xmv_post: no_src


# SRC: "Strings of length 1 or less are not valid."
def test_empty_string_is_invalid():
    pass  # deleted by xmv_post: no_src


# SRC: "Strings of length 1 or less are not valid."
def test_length_two_is_checked_not_rejected():
    pass  # deleted by xmv_post: no_src


# SRC: "Spaces are allowed in the input, but they should be stripped before checking."
def test_leading_and_trailing_spaces_are_stripped():
    pass  # deleted by xmv_post: no_src


# SRC: "Spaces are allowed in the input, but they should be stripped before checking."
def test_spaces_do_not_change_result():
    pass  # deleted by xmv_post: no_src


# SRC: "Strings of length 1 or less are not valid."
def test_only_spaces_around_single_digit_is_invalid():
    pass  # deleted by xmv_post: no_src


# SRC: "All other non-digit characters are disallowed."
def test_non_digit_character_is_invalid():
    pass  # deleted by xmv_post: no_src


# SRC: "If the result of doubling a digit is greater than 9, we subtract 9 from that result."
def test_doubled_digit_above_nine_has_nine_subtracted():
    pass  # deleted by xmv_post: no_src


# SRC: "If the sum is evenly divisible by 10, the original number is valid."
def test_odd_length_number_is_valid():
    pass  # deleted by xmv_post: no_src


# SRC: "If the sum is evenly divisible by 10, the original number is valid."
def test_sum_not_divisible_by_ten_is_invalid():
    pass  # deleted by xmv_post: no_src


# SRC: "If the sum is evenly divisible by 10, the original number is valid."
def test_sum_of_zero_is_divisible_by_ten_and_valid():
    pass  # deleted by xmv_post: no_src
