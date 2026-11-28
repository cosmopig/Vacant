from custom_set import CustomSet


def test_new_set_without_elements_is_empty():
    """REQ: "Create a custom set type."

    A set created with no elements contains nothing, so isempty() returns True.
    """
    assert CustomSet().isempty() is True


def test_set_created_with_elements_is_not_empty():
    """REQ: "as long as it behaves like a set of unique elements."

    A set created with elements is not empty, so isempty() returns False.
    """
    assert CustomSet([1, 2, 3]).isempty() is False


def test_add_makes_element_present():
    """REQ: "as long as it behaves like a set of unique elements."

    After add(), the element is contained in the set and the set is no longer empty.
    """
    cs = CustomSet()
    cs.add("a")
    assert "a" in cs
    assert cs.isempty() is False


def test_contains_true_for_constructor_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    Each element passed to the constructor is contained in the set.
    """
    cs = CustomSet([1, 2, 3])
    assert 1 in cs
    assert 2 in cs
    assert 3 in cs


def test_contains_false_for_absent_element():
    """REQ: "as long as it behaves like a set of unique elements."

    An element that was never added is not contained in the set.
    """
    cs = CustomSet([1, 2])
    assert 3 not in cs


def test_constructor_removes_duplicate_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    Duplicate elements given to the constructor are stored once, so [1, 1, 2, 2, 2]
    equals the set {1, 2}.
    """
    assert CustomSet([1, 1, 2, 2, 2]) == CustomSet([1, 2])


def test_add_duplicate_does_not_change_set():
    """REQ: "as long as it behaves like a set of unique elements."

    Adding an element that is already present leaves the set equal to a set with
    only that element, no matter how many times it is added.
    """
    cs = CustomSet([5])
    cs.add(5)
    assert cs == CustomSet([5])
    cs.add(5)
    assert cs == CustomSet([5])


def test_empty_sets_are_equal():
    """REQ: "as long as it behaves like a set of unique elements."

    Two sets with no elements are equal.
    """
    assert CustomSet() == CustomSet()


def test_equality_ignores_order_of_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    A set has no ordering, so {1, 2, 3} equals {3, 1, 2}.
    """
    assert CustomSet([1, 2, 3]) == CustomSet([3, 1, 2])


def test_equality_false_for_different_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    Sets with different sets of elements are not equal.
    """
    assert not (CustomSet([1, 2]) == CustomSet([1, 3]))
    assert not (CustomSet([1, 2]) == CustomSet([1]))


def test_empty_set_is_subset_of_any_set():
    """REQ: "as long as it behaves like a set of unique elements."

    The empty set has no elements outside any other set, so it is a subset of it.
    """
    assert CustomSet().issubset(CustomSet([1, 2])) is True


def test_subset_true_when_all_elements_are_contained():
    """REQ: "as long as it behaves like a set of unique elements."

    {1, 2} is a subset of {1, 2, 3}, and every set is a subset of an equal set.
    """
    assert CustomSet([1, 2]).issubset(CustomSet([1, 2, 3])) is True
    assert CustomSet([1, 2]).issubset(CustomSet([2, 1])) is True


def test_subset_false_when_an_element_is_missing():
    """REQ: "as long as it behaves like a set of unique elements."

    {1, 4} is not a subset of {1, 2, 3} because 4 is missing, and the larger set
    {1, 2, 3} is not a subset of {1, 2}.
    """
    assert CustomSet([1, 4]).issubset(CustomSet([1, 2, 3])) is False
    assert CustomSet([1, 2, 3]).issubset(CustomSet([1, 2])) is False


def test_nonempty_set_is_not_subset_of_empty_set():
    """REQ: "as long as it behaves like a set of unique elements."

    A set with an element cannot be a subset of the empty set.
    """
    assert CustomSet([1]).issubset(CustomSet()) is False


def test_disjoint_true_when_no_common_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    {1, 2} and {3, 4} share no elements, so they are disjoint. The empty set is
    disjoint from every set.
    """
    assert CustomSet([1, 2]).isdisjoint(CustomSet([3, 4])) is True
    assert CustomSet().isdisjoint(CustomSet([3])) is True


def test_disjoint_false_when_common_element_exists():
    """REQ: "as long as it behaves like a set of unique elements."

    {1, 2} and {2, 3} share the element 2, so they are not disjoint.
    """
    assert CustomSet([1, 2]).isdisjoint(CustomSet([2, 3])) is False


def test_intersection_returns_common_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    The intersection of {1, 2, 3} and {2, 3, 4} contains 2 and 3 only.
    """
    result = CustomSet([1, 2, 3]).intersection(CustomSet([2, 3, 4]))
    assert 2 in result
    assert 3 in result
    assert 1 not in result
    assert 4 not in result


def test_intersection_of_disjoint_sets_is_empty():
    """REQ: "as long as it behaves like a set of unique elements."

    The intersection of two disjoint sets has no elements.
    """
    result = CustomSet([1]).intersection(CustomSet([2]))
    assert result.isempty() is True


def test_subtraction_returns_elements_only_in_left_operand():
    """REQ: "as long as it behaves like a set of unique elements."

    {1, 2, 3} minus {2, 4} keeps the elements 1 and 3 and drops 2. The element 4 is
    not in the left operand, so it is not in the result.
    """
    result = CustomSet([1, 2, 3]) - CustomSet([2, 4])
    assert 1 in result
    assert 3 in result
    assert 2 not in result
    assert 4 not in result


def test_addition_returns_union_of_elements():
    """REQ: "as long as it behaves like a set of unique elements."

    {1, 2} plus {2, 3} is the union {1, 2, 3}, which contains 1, 2 and 3 but not 4.
    """
    result = CustomSet([1, 2]) + CustomSet([2, 3])
    assert 1 in result
    assert 2 in result
    assert 3 in result
    assert 4 not in result


def test_separate_instances_do_not_share_state():
    """REQ: "Create a custom set type."

    Each set is its own object. Elements added to one set do not appear in a set
    created later.
    """
    a = CustomSet()
    a.add(1)
    b = CustomSet()
    assert 1 not in b
    assert b.isempty() is True
    c = CustomSet([7])
    d = CustomSet()
    assert 7 not in d
