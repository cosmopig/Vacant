"""Acceptance tests for the say() number-to-words exercise."""

import pytest

from say import say


MAX_VALUE = 999_999_999_999


def _norm(text):
    """Collapse commas and runs of whitespace so punctuation style does not matter."""
    return " ".join(text.replace(",", " ").split())


def test_returns_nonempty_string_for_valid_input():
    """REQ: "Given a number, your task is to express it in English words exactly as your friend should say it out loud." """
    for number in (0, 1, 12, 123, 1234, MAX_VALUE):
        result = say(number)
        assert isinstance(result, str), f"say({number}) returned {type(result).__name__}, expected str"
        assert result.strip() != "", f"say({number}) returned an empty string"


def test_zero_example():
    """REQ: "0 → zero" """
    assert say(0) == "zero"


def test_one_example():
    """REQ: "1 → one" """
    assert say(1) == "one"


def test_twelve_example():
    """REQ: "12 → twelve" """
    assert say(12) == "twelve"


def test_one_hundred_twenty_three_example():
    """REQ: "123 → one hundred twenty-three" """
    assert say(123) == "one hundred twenty-three"


def test_one_thousand_two_hundred_thirty_four_example():
    """REQ: "1,234 → one thousand two hundred thirty-four" """
    assert say(1234) == "one thousand two hundred thirty-four"


def test_teens_are_single_words():
    """REQ: "Given a number, your task is to express it in English words exactly as your friend should say it out loud." """
    expected = {11: "eleven", 13: "thirteen", 15: "fifteen", 19: "nineteen"}
    for number, words in expected.items():
        assert say(number) == words, f"say({number}) should be {words!r}"


def test_tens_and_hyphenated_compounds():
    """REQ: "123 → one hundred twenty-three" """
    expected = {
        20: "twenty",
        21: "twenty-one",
        90: "ninety",
        99: "ninety-nine",
    }
    for number, words in expected.items():
        assert say(number) == words, f"say({number}) should be {words!r}"


def test_hundreds_with_and_without_remainder():
    """REQ: "123 → one hundred twenty-three" """
    expected = {
        100: "one hundred",
        700: "seven hundred",
        999: "nine hundred ninety-nine",
    }
    for number, words in expected.items():
        assert say(number) == words, f"say({number}) should be {words!r}"


def test_thousand_million_billion_scales():
    """REQ: "1,234 → one thousand two hundred thirty-four" """
    assert say(1000) == "one thousand"
    assert say(100000) == "one hundred thousand"
    assert say(1000000) == "one million"
    assert say(1000000000) == "one billion"


def test_zero_groups_are_not_spoken_as_words():
    """REQ: "1,234 → one thousand two hundred thirty-four" """
    assert _norm(say(1001)) == "one thousand one"
    assert _norm(say(1000001)) == "one million one"
    assert _norm(say(1000000001)) == "one billion one"


def test_upper_bound_is_accepted():
    """REQ: "Yaʻqūb expects to use numbers from 0 up to 999,999,999,999." """
    expected = (
        "nine hundred ninety-nine billion nine hundred ninety-nine million "
        "nine hundred ninety-nine thousand nine hundred ninety-nine"
    )
    assert _norm(say(MAX_VALUE)) == expected


def test_negative_number_raises_value_error_with_message():
    """REQ: "# if the number is negative" """
    with pytest.raises(ValueError) as excinfo:
        say(-1)
    assert str(excinfo.value).strip() != "", "ValueError for negative input has no message"


def test_number_above_upper_bound_raises_value_error_with_message():
    """REQ: "# if the number is larger than 999,999,999,999" """
    with pytest.raises(ValueError) as excinfo:
        say(MAX_VALUE + 1)
    assert str(excinfo.value).strip() != "", "ValueError for too-large input has no message"


def test_out_of_range_errors_carry_a_message():
    """REQ: "The tests will only pass if you both `raise` the `exception` and include a message with it." """
    for bad in (-1, MAX_VALUE + 1):
        with pytest.raises(ValueError) as excinfo:
            say(bad)
        message = str(excinfo.value)
        assert isinstance(message, str) and message.strip() != "", (
            f"say({bad}) raised ValueError without a meaningful message"
        )


def test_output_contains_only_words_and_separators():
    """REQ: "express it in English words" """
    samples = list(range(0, 1201)) + [MAX_VALUE, 1000000, 1000000000]
    for number in samples:
        result = say(number)
        for ch in result:
            assert ch.isalpha() or ch in " -,", (
                f"say({number}) contains unexpected character {ch!r} in {result!r}"
            )
