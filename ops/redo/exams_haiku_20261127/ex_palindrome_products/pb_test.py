"""Acceptance tests for the palindrome_products exercise.

Each test_ function checks one property taken from the requirements text.
"""

import pytest

from palindrome_products import largest, smallest


def _is_palindrome(n):
    s = str(n)
    return s == s[::-1]


def _pairs(factors):
    """Normalise a factors iterable into a set of sorted (a, b) tuples.

    Accepts either a flat two-element iterable of ints (one pair) or an
    iterable of two-element iterables (several pairs).
    """
    items = list(factors)
    if len(items) == 2 and all(isinstance(x, int) for x in items):
        return {tuple(sorted(items))}
    return {tuple(sorted(p)) for p in items}


def _factors_are_well_formed(factors):
    items = list(factors)
    if len(items) == 2 and all(isinstance(x, int) for x in items):
        return True
    return len(items) >= 1 and all(
        len(list(p)) == 2 and all(isinstance(x, int) for x in p) for p in items
    )


def test_largest_returns_value_and_iterable_of_factors():
    """REQ: "Their return value must be a `tuple -- (value, factors)` where `value` is the palindrome itself, and `factors` is an `iterable` containing both factors of the palindrome in arbitrary order." """
    result = largest(max_factor=9)
    assert isinstance(result, tuple)
    assert len(result) == 2
    value, factors = result
    assert isinstance(value, int)
    assert iter(factors) is not None
    assert _factors_are_well_formed(factors)


def test_smallest_returns_value_and_iterable_of_factors():
    """REQ: "Their return value must be a `tuple -- (value, factors)` where `value` is the palindrome itself, and `factors` is an `iterable` containing both factors of the palindrome in arbitrary order." """
    result = smallest(max_factor=9)
    assert isinstance(result, tuple)
    assert len(result) == 2
    value, factors = result
    assert isinstance(value, int)
    assert iter(factors) is not None
    assert _factors_are_well_formed(factors)


def test_example_1_largest_in_1_to_9():
    """REQ: "The largest palindrome product is `9`. Its factors are `(1, 9)` and `(3, 3)`." """
    value, factors = largest(min_factor=1, max_factor=9)
    assert value == 9
    assert _pairs(factors) == {(1, 9), (3, 3)}


def test_example_1_smallest_in_1_to_9():
    """REQ: "The smallest palindrome product is `1`. Its factors are `(1, 1)`." """
    value, factors = smallest(min_factor=1, max_factor=9)
    assert value == 1
    assert _pairs(factors) == {(1, 1)}


def test_example_2_smallest_in_10_to_99():
    """REQ: "The smallest palindrome product is `121`. Its factors are `(11, 11)`." """
    value, factors = smallest(min_factor=10, max_factor=99)
    assert value == 121
    assert _pairs(factors) == {(11, 11)}


def test_example_2_largest_in_10_to_99():
    """REQ: "The largest palindrome product is `9009`. Its factors are `(91, 99)`." """
    value, factors = largest(min_factor=10, max_factor=99)
    assert value == 9009
    assert _pairs(factors) == {(91, 99)}


def test_largest_value_is_palindrome_and_factors_multiply_into_range():
    """REQ: "Given a range of numbers, find the largest and smallest palindromes which are products of two numbers within that range." """
    for lo, hi in [(1, 9), (10, 99), (100, 999)]:
        value, factors = largest(min_factor=lo, max_factor=hi)
        assert _is_palindrome(value)
        for a, b in _pairs(factors):
            assert lo <= a <= hi
            assert lo <= b <= hi
            assert a * b == value


def test_smallest_value_is_palindrome_and_factors_multiply_into_range():
    """REQ: "Given a range of numbers, find the largest and smallest palindromes which are products of two numbers within that range." """
    for lo, hi in [(1, 9), (10, 99), (100, 999)]:
        value, factors = smallest(min_factor=lo, max_factor=hi)
        assert _is_palindrome(value)
        for a, b in _pairs(factors):
            assert lo <= a <= hi
            assert lo <= b <= hi
            assert a * b == value


def test_smallest_is_not_greater_than_largest():
    """REQ: "find the largest and smallest palindromes which are products of two numbers within that range." """
    for lo, hi in [(1, 9), (10, 99), (100, 999)]:
        small_value, _ = smallest(min_factor=lo, max_factor=hi)
        large_value, _ = largest(min_factor=lo, max_factor=hi)
        assert small_value <= large_value


def test_three_digit_range_extremes():
    """REQ: "Given a range of numbers, find the largest and smallest palindromes which are products of two numbers within that range." """
    value, factors = largest(min_factor=100, max_factor=999)
    assert value == 906609
    assert _pairs(factors) == {(913, 993)}

    value, factors = smallest(min_factor=100, max_factor=999)
    assert value == 10201
    assert _pairs(factors) == {(101, 101)}


def test_single_product_range_returns_that_square():
    """REQ: "Given a range of numbers, find the largest and smallest palindromes which are products of two numbers within that range." """
    for func in (largest, smallest):
        value, factors = func(min_factor=11, max_factor=11)
        assert value == 121
        assert _pairs(factors) == {(11, 11)}


def test_min_factor_defaults_to_zero():
    """REQ: "Both functions must take two keyword arguments: `max_factor`: int, `min_factor`: int, default 0" """
    assert largest(max_factor=9) == largest(min_factor=0, max_factor=9)
    value, factors = largest(max_factor=9)
    assert value == 9
    assert _pairs(factors) == {(1, 9), (3, 3)}


def test_keyword_arguments_are_accepted():
    """REQ: "Both functions must take two keyword arguments: `max_factor`: int, `min_factor`: int, default 0" """
    value, factors = smallest(min_factor=10, max_factor=99)
    assert value == 121
    assert _pairs(factors) == {(11, 11)}
    value, factors = largest(min_factor=10, max_factor=99)
    assert value == 9009
    assert _pairs(factors) == {(91, 99)}


def test_largest_raises_value_error_with_message_when_min_exceeds_max():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a `ValueError` when the `largest()` or `smallest()` function receives a pair of factors that are not in the correct range." """
    with pytest.raises(ValueError) as info:
        largest(min_factor=9, max_factor=1)
    assert str(info.value).strip() != ""


def test_smallest_raises_value_error_with_message_when_min_exceeds_max():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a `ValueError` when the `largest()` or `smallest()` function receives a pair of factors that are not in the correct range." """
    with pytest.raises(ValueError) as info:
        smallest(min_factor=9, max_factor=1)
    assert str(info.value).strip() != ""


def test_results_are_deterministic_across_calls():
    """REQ: "Given a range of numbers, find the largest and smallest palindromes which are products of two numbers within that range." """
    first_large = largest(min_factor=10, max_factor=99)
    second_large = largest(min_factor=10, max_factor=99)
    assert first_large[0] == second_large[0]
    assert _pairs(first_large[1]) == _pairs(second_large[1])

    first_small = smallest(min_factor=10, max_factor=99)
    second_small = smallest(min_factor=10, max_factor=99)
    assert first_small[0] == second_small[0]
    assert _pairs(first_small[1]) == _pairs(second_small[1])
