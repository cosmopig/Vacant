import pytest

from palindrome_products import largest, smallest


def _is_palindrome(n):
    s = str(n)
    return s == s[::-1]


def _pairs(factors):
    """Normalise the returned factors into a set of sorted (a, b) tuples.

    A flat iterable of two ints is treated as a single pair. Otherwise the
    iterable is expected to hold one pair per element.
    """
    items = list(factors)
    if len(items) == 2 and all(isinstance(x, int) for x in items):
        return {tuple(sorted(items))}
    return {tuple(sorted(pair)) for pair in items}


def _assert_result(result, value, expected_pairs, min_f, max_f):
    assert isinstance(result, tuple)
    assert len(result) == 2
    got_value, factors = result
    assert got_value == value
    assert _is_palindrome(got_value)
    pairs = _pairs(factors)
    assert pairs == expected_pairs
    for a, b in pairs:
        assert a * b == value
        assert min_f <= a <= max_f
        assert min_f <= b <= max_f


def test_smallest_single_digit_range():
    _assert_result(
        smallest(min_factor=1, max_factor=9),
        value=1,
        expected_pairs={(1, 1)},
        min_f=1,
        max_f=9,
    )


def test_largest_single_digit_range_returns_all_pairs():
    _assert_result(
        largest(min_factor=1, max_factor=9),
        value=9,
        expected_pairs={(1, 9), (3, 3)},
        min_f=1,
        max_f=9,
    )


def test_largest_min_factor_defaults_to_zero():
    result = largest(max_factor=9)
    _assert_result(
        result,
        value=9,
        expected_pairs={(1, 9), (3, 3)},
        min_f=0,
        max_f=9,
    )


def test_smallest_two_digit_range():
    _assert_result(
        smallest(min_factor=10, max_factor=99),
        value=121,
        expected_pairs={(11, 11)},
        min_f=10,
        max_f=99,
    )


def test_largest_two_digit_range():
    _assert_result(
        largest(min_factor=10, max_factor=99),
        value=9009,
        expected_pairs={(91, 99)},
        min_f=10,
        max_f=99,
    )


def test_single_value_range_palindrome_is_both_smallest_and_largest():
    _assert_result(
        smallest(min_factor=11, max_factor=11),
        value=121,
        expected_pairs={(11, 11)},
        min_f=11,
        max_f=11,
    )
    _assert_result(
        largest(min_factor=11, max_factor=11),
        value=121,
        expected_pairs={(11, 11)},
        min_f=11,
        max_f=11,
    )


def test_range_of_one_element_one():
    _assert_result(
        smallest(min_factor=1, max_factor=1),
        value=1,
        expected_pairs={(1, 1)},
        min_f=1,
        max_f=1,
    )
    _assert_result(
        largest(min_factor=1, max_factor=1),
        value=1,
        expected_pairs={(1, 1)},
        min_f=1,
        max_f=1,
    )


def test_range_where_smallest_and_largest_coincide():
    # Products within [3, 9] that are palindromes: only 9 = 3 * 3.
    _assert_result(
        smallest(min_factor=3, max_factor=9),
        value=9,
        expected_pairs={(3, 3)},
        min_f=3,
        max_f=9,
    )
    _assert_result(
        largest(min_factor=3, max_factor=9),
        value=9,
        expected_pairs={(3, 3)},
        min_f=3,
        max_f=9,
    )


def test_largest_raises_value_error_when_min_greater_than_max():
    with pytest.raises(ValueError) as excinfo:
        largest(min_factor=9, max_factor=1)
    assert str(excinfo.value).strip() != ""


def test_smallest_raises_value_error_when_min_greater_than_max():
    with pytest.raises(ValueError) as excinfo:
        smallest(min_factor=9, max_factor=1)
    assert str(excinfo.value).strip() != ""
