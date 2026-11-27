"""Acceptance tests for the CustomSet exercise.

Only behaviour stated in, or clearly implied by, the requirements text is
checked. The requirements say the type must behave like a set of unique
elements, so the operator and method semantics below follow Python's built-in
set. The __add__ method is not tested because the requirements do not define it.
"""

from custom_set import CustomSet


def test_custom_set_type_can_be_created():
    # SRC: "Create a custom set type."
    assert isinstance(CustomSet([]), CustomSet)


def test_empty_set_is_empty():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([]).isempty()


def test_non_empty_set_is_not_empty():
    # SRC: "behaves like a set of unique elements"
    assert not CustomSet([1]).isempty()


def test_duplicate_elements_are_stored_once():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 1, 2]) == CustomSet([1, 2])


def test_duplicate_elements_do_not_make_set_non_empty_when_only_duplicates_given():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 1]) == CustomSet([1])


def test_membership_of_present_element():
    # SRC: "behaves like a set of unique elements"
    assert 2 in CustomSet([1, 2])


def test_membership_of_absent_element():
    # SRC: "behaves like a set of unique elements"
    assert 3 not in CustomSet([1, 2])


def test_add_inserts_new_element():
    s = CustomSet([1])
    s.add(2)
    # SRC: "behaves like a set of unique elements"
    assert 2 in s


def test_add_existing_element_keeps_set_unchanged():
    s = CustomSet([1, 2])
    s.add(2)
    # SRC: "behaves like a set of unique elements"
    assert s == CustomSet([1, 2])


def test_equality_ignores_order():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 2]) == CustomSet([2, 1])


def test_equality_of_different_sets_is_false():
    # SRC: "behaves like a set of unique elements"
    assert not (CustomSet([1, 2]) == CustomSet([1]))


def test_equality_of_two_empty_sets():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([]) == CustomSet([])


def test_subset_of_larger_set():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1]).issubset(CustomSet([1, 2]))


def test_larger_set_is_not_subset_of_smaller_set():
    # SRC: "behaves like a set of unique elements"
    assert not CustomSet([1, 2]).issubset(CustomSet([1]))


def test_empty_set_is_subset_of_any_set():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([]).issubset(CustomSet([1]))


def test_set_is_subset_of_itself():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 2]).issubset(CustomSet([1, 2]))


def test_disjoint_sets():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 2]).isdisjoint(CustomSet([3, 4]))


def test_sets_sharing_an_element_are_not_disjoint():
    # SRC: "behaves like a set of unique elements"
    assert not CustomSet([1, 2]).isdisjoint(CustomSet([2, 3]))


def test_empty_set_is_disjoint_from_any_set():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([]).isdisjoint(CustomSet([1]))


def test_intersection_of_overlapping_sets():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 2]).intersection(CustomSet([2, 3])) == CustomSet([2])


def test_intersection_of_disjoint_sets_is_empty():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1]).intersection(CustomSet([2])) == CustomSet([])


def test_subtraction_removes_common_elements():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1, 2, 3]) - CustomSet([2]) == CustomSet([1, 3])


def test_subtraction_of_absent_elements_changes_nothing():
    # SRC: "behaves like a set of unique elements"
    assert CustomSet([1]) - CustomSet([2]) == CustomSet([1])
