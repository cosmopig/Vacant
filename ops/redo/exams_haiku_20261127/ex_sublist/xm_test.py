from sublist import sublist, SUBLIST, SUPERLIST, EQUAL, UNEQUAL


def test_both_empty_lists_are_equal():
    assert sublist([], []) == EQUAL


def test_identical_nonempty_lists_are_equal():
    assert sublist([1, 2, 3], [1, 2, 3]) == EQUAL
    assert sublist([1], [1]) == EQUAL


def test_empty_list_is_sublist_of_nonempty_list():
    assert sublist([], [1, 2, 3]) == SUBLIST


def test_nonempty_list_is_superlist_of_empty_list():
    assert sublist([1, 2, 3], []) == SUPERLIST


def test_sublist_at_start_of_longer_list():
    assert sublist([1, 2, 3], [1, 2, 3, 4, 5]) == SUBLIST


def test_sublist_at_end_of_longer_list():
    assert sublist([3, 4, 5], [1, 2, 3, 4, 5]) == SUBLIST


def test_sublist_in_middle_of_longer_list():
    assert sublist([3, 4], [1, 2, 3, 4, 5]) == SUBLIST


def test_superlist_contains_contiguous_run_in_middle():
    assert sublist([1, 2, 3, 4, 5], [2, 3, 4]) == SUPERLIST


def test_superlist_contains_run_at_end():
    assert sublist([1, 2, 3, 4, 5], [4, 5]) == SUPERLIST


def test_single_element_superlist_and_sublist():
    assert sublist([1, 2, 3], [2]) == SUPERLIST
    assert sublist([2], [1, 2, 3]) == SUBLIST


def test_same_length_different_values_are_unequal():
    assert sublist([1, 2, 3], [4, 5, 6]) == UNEQUAL


def test_values_present_but_not_contiguous_are_unequal():
    assert sublist([1, 2, 4], [1, 2, 3, 4, 5]) == UNEQUAL
    assert sublist([1, 2, 3, 4, 5], [1, 3, 5]) == UNEQUAL


def test_order_matters_for_equality():
    assert sublist([1, 2, 3], [1, 3, 2]) == UNEQUAL


def test_repeated_values_require_contiguous_match():
    assert sublist([1, 1, 2], [1, 1, 1, 2]) == SUBLIST
    assert sublist([1, 1, 1, 2], [1, 1, 2]) == SUPERLIST
