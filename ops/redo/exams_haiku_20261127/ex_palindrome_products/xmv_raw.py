import pytest

from palindrome_products import largest, smallest


def _sorted_factors(result):
    return tuple(sorted(result[1]))


def test_largest_over_range_1_to_9_is_9():
    # SRC: "The largest palindrome product is `9`."
    assert largest(min_factor=1, max_factor=9)[0] == 9


def test_largest_over_range_1_to_9_factors_are_a_valid_pair():
    # SRC: "Its factors are `(1, 9)` and `(3, 3)`."
    assert _sorted_factors(largest(min_factor=1, max_factor=9)) in {(1, 9), (3, 3)}


def test_smallest_over_range_1_to_9_is_1():
    # SRC: "The smallest palindrome product is `1`."
    assert smallest(min_factor=1, max_factor=9)[0] == 1


def test_smallest_over_range_1_to_9_factors_are_1_and_1():
    # SRC: "Its factors are `(1, 1)`."
    assert _sorted_factors(smallest(min_factor=1, max_factor=9)) == (1, 1)


def test_smallest_over_range_10_to_99_is_121():
    # SRC: "The smallest palindrome product is `121`."
    assert smallest(min_factor=10, max_factor=99)[0] == 121


def test_smallest_over_range_10_to_99_factors_are_11_and_11():
    # SRC: "Its factors are `(11, 11)`."
    assert _sorted_factors(smallest(min_factor=10, max_factor=99)) == (11, 11)


def test_largest_over_range_10_to_99_is_9009():
    # SRC: "The largest palindrome product is `9009`."
    assert largest(min_factor=10, max_factor=99)[0] == 9009


def test_largest_over_range_10_to_99_factors_are_91_and_99():
    # SRC: "Its factors are `(91, 99)`."
    assert _sorted_factors(largest(min_factor=10, max_factor=99)) == (91, 99)


def test_return_value_is_a_two_item_tuple():
    # SRC: "Their return value must be a `tuple -- (value, factors)`"
    assert isinstance(largest(min_factor=1, max_factor=9), tuple)
    # SRC: "Their return value must be a `tuple -- (value, factors)`"
    assert len(largest(min_factor=1, max_factor=9)) == 2


def test_min_factor_defaults_to_zero_for_largest():
    # SRC: "- `min_factor`: int, default 0"
    assert largest(max_factor=9)[0] == 9


def test_range_bounds_are_inclusive_for_single_element_range():
    # SRC: "Given the range `[1, 9]` (both inclusive)..."
    assert largest(min_factor=1, max_factor=1)[0] == 1


def test_largest_raises_value_error_when_min_greater_than_max():
    # SRC: "# if the max_factor is less than the min_factor"
    with pytest.raises(ValueError):
        largest(min_factor=10, max_factor=1)


def test_smallest_raises_value_error_with_message_when_min_greater_than_max():
    # SRC: "a `ValueError` when the `largest()` or `smallest()` function receives a pair of factors that are not in the correct range."
    with pytest.raises(ValueError) as excinfo:
        smallest(min_factor=10, max_factor=1)
    # SRC: "you should always include a **meaningful error message** to indicate what the source of the error is."
    assert str(excinfo.value).strip() != ""
