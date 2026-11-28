"""Acceptance tests for the sublist exercise.

Each check function covers one property taken from the requirements text.
"""

from sublist import SUBLIST, SUPERLIST, EQUAL, UNEQUAL, sublist


ALL_CATEGORIES = (SUBLIST, SUPERLIST, EQUAL, UNEQUAL)


def test_categories_are_four_distinct_values():
    """REQ: "None of the above is true, thus lists A and B are unequal" (the four outcomes must be distinguishable)."""
    values = [SUBLIST, SUPERLIST, EQUAL, UNEQUAL]
    assert len(set(values)) == 4


def test_result_is_always_one_of_the_four_categories():
    """REQ: "Given any two lists A and B, determine if: ... None of the above is true" (every answer is one of the four outcomes)."""
    pairs = [
        ([], []),
        ([1, 2, 3], []),
        ([], [1, 2, 3]),
        ([1, 2, 3], [1, 2, 3, 4, 5]),
        ([1, 2, 4], [1, 2, 3, 4, 5]),
    ]
    for a, b in pairs:
        assert sublist(a, b) in ALL_CATEGORIES


def test_result_is_deterministic_for_same_input():
    """REQ: "Given any two lists A and B, determine if:" (the answer is a function of the inputs alone)."""
    first = sublist([3, 4], [1, 2, 3, 4, 5])
    second = sublist([3, 4], [1, 2, 3, 4, 5])
    assert first == second == SUBLIST


def test_two_empty_lists_are_equal():
    """REQ: "If A = [] and B = [] (both lists are empty), then A and B are equal" """
    assert sublist([], []) == EQUAL


def test_nonempty_list_is_superlist_of_empty_list():
    """REQ: "If A = [1, 2, 3] and B = [], then A is a superlist of B" """
    assert sublist([1, 2, 3], []) == SUPERLIST


def test_empty_list_is_sublist_of_nonempty_list():
    """REQ: "If A = [] and B = [1, 2, 3], then A is a sublist of B" """
    assert sublist([], [1, 2, 3]) == SUBLIST


def test_prefix_of_longer_list_is_sublist():
    """REQ: "If A = [1, 2, 3] and B = [1, 2, 3, 4, 5], then A is a sublist of B" """
    assert sublist([1, 2, 3], [1, 2, 3, 4, 5]) == SUBLIST


def test_contiguous_tail_of_longer_list_is_sublist():
    """REQ: "If A = [3, 4, 5] and B = [1, 2, 3, 4, 5], then A is a sublist of B" """
    assert sublist([3, 4, 5], [1, 2, 3, 4, 5]) == SUBLIST


def test_contiguous_middle_run_is_sublist():
    """REQ: "If A = [3, 4] and B = [1, 2, 3, 4, 5], then A is a sublist of B" """
    assert sublist([3, 4], [1, 2, 3, 4, 5]) == SUBLIST


def test_identical_lists_are_equal():
    """REQ: "If A = [1, 2, 3] and B = [1, 2, 3], then A and B are equal" """
    assert sublist([1, 2, 3], [1, 2, 3]) == EQUAL


def test_longer_list_containing_middle_run_is_superlist():
    """REQ: "If A = [1, 2, 3, 4, 5] and B = [2, 3, 4], then A is a superlist of B" """
    assert sublist([1, 2, 3, 4, 5], [2, 3, 4]) == SUPERLIST


def test_longer_list_containing_run_at_end_is_superlist():
    """REQ: "List A is a superlist of B if A contains a contiguous sub-sequence of values equal to B" (match at the end of A)."""
    assert sublist([1, 2, 3, 4, 5], [4, 5]) == SUPERLIST


def test_longer_list_containing_run_at_start_is_superlist():
    """REQ: "List A is a superlist of B if A contains a contiguous sub-sequence of values equal to B" (match at the start of A)."""
    assert sublist([1, 2, 3, 4, 5], [1, 2]) == SUPERLIST


def test_missing_value_makes_lists_unequal():
    """REQ: "If A = [1, 2, 4] and B = [1, 2, 3, 4, 5], then A and B are unequal" """
    assert sublist([1, 2, 4], [1, 2, 3, 4, 5]) == UNEQUAL


def test_same_values_in_different_order_are_unequal():
    """REQ: "If A = [1, 2, 3] and B = [1, 3, 2], then A and B are unequal" """
    assert sublist([1, 2, 3], [1, 3, 2]) == UNEQUAL


def test_same_length_with_one_differing_value_is_unequal():
    """REQ: "List A is equal to list B if both lists have the same values in the same order" (a single differing value breaks equality)."""
    assert sublist([1, 2, 3], [1, 2, 4]) == UNEQUAL


def test_swapping_arguments_swaps_sublist_and_superlist():
    """REQ: "List A is a superlist of B if A contains ... List A is a sublist of B if B contains ..." (the two relations are mirror images)."""
    a, b = [1, 2, 3], [1, 2, 3, 4, 5]
    assert sublist(a, b) == SUBLIST
    assert sublist(b, a) == SUPERLIST


def test_nonempty_list_equals_itself():
    """REQ: "List A is equal to list B if both lists have the same values in the same order" (a list equals itself)."""
    a = [7, 8, 9]
    assert sublist(a, list(a)) == EQUAL


def test_single_differing_element_lists_are_unequal():
    """REQ: "None of the above is true, thus lists A and B are unequal" (single-element lists with different values)."""
    assert sublist([1], [2]) == UNEQUAL


def test_single_element_contained_in_longer_list_is_sublist():
    """REQ: "List A is a sublist of B if B contains a contiguous sub-sequence of values equal to A" (single-element boundary)."""
    assert sublist([3], [1, 2, 3, 4, 5]) == SUBLIST


def test_repeated_values_superlist_is_detected():
    """REQ: "List A is a superlist of B if A contains a contiguous sub-sequence of values equal to B" (repeated values must still match)."""
    assert sublist([1, 1, 2], [1, 2]) == SUPERLIST


def test_repeated_values_sublist_is_detected():
    """REQ: "List A is a sublist of B if B contains a contiguous sub-sequence of values equal to A" (repeated values must still match)."""
    assert sublist([1, 2], [1, 1, 2]) == SUBLIST


def test_values_separated_in_other_list_are_unequal():
    """REQ: "List A is a sublist of B if B contains a contiguous sub-sequence of values equal to A" (non-contiguous values do not count)."""
    assert sublist([1, 2], [1, 3, 2]) == UNEQUAL


def test_works_for_string_values():
    """REQ: "Given any two lists A and B" (values other than integers are allowed)."""
    assert sublist(["a", "b"], ["a", "b"]) == EQUAL
    assert sublist(["a", "b", "c"], ["b"]) == SUPERLIST
    assert sublist(["b"], ["a", "b", "c"]) == SUBLIST
