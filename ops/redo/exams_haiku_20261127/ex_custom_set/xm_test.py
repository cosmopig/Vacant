from custom_set import CustomSet


def test_new_set_is_empty():
    assert CustomSet().isempty()


def test_set_with_elements_is_not_empty():
    assert not CustomSet([1]).isempty()


def test_zero_is_a_normal_element():
    assert not CustomSet([0]).isempty()
    assert 0 in CustomSet([0])


def test_nothing_is_contained_in_empty_set():
    assert 1 not in CustomSet()


def test_contains_present_and_absent_elements():
    s = CustomSet([1, 2, 3])
    assert 2 in s
    assert 4 not in s


def test_duplicates_are_collapsed():
    assert CustomSet([1, 1]) == CustomSet([1])
    assert CustomSet([1, 2, 1, 2]) == CustomSet([2, 1])


def test_add_to_empty_set():
    s = CustomSet()
    s.add(1)
    assert 1 in s
    assert not s.isempty()
    assert s == CustomSet([1])


def test_add_existing_element_does_not_duplicate():
    s = CustomSet([1])
    s.add(1)
    assert s == CustomSet([1])


def test_empty_set_is_subset_of_any_set():
    assert CustomSet().issubset(CustomSet([1, 2]))
    assert CustomSet().issubset(CustomSet())


def test_non_empty_set_is_not_subset_of_empty_set():
    assert not CustomSet([1]).issubset(CustomSet())


def test_set_is_subset_of_equal_set():
    assert CustomSet([1, 2]).issubset(CustomSet([1, 2]))


def test_set_is_subset_of_larger_set():
    assert CustomSet([1]).issubset(CustomSet([1, 2]))


def test_larger_set_is_not_subset_of_smaller_set():
    assert not CustomSet([1, 2]).issubset(CustomSet([1]))


def test_sets_with_no_common_elements_are_disjoint():
    assert CustomSet([1, 2]).isdisjoint(CustomSet([3, 4]))


def test_sets_sharing_an_element_are_not_disjoint():
    assert not CustomSet([1, 2]).isdisjoint(CustomSet([2, 3]))


def test_empty_set_is_disjoint_from_everything():
    assert CustomSet().isdisjoint(CustomSet([1]))
    assert CustomSet().isdisjoint(CustomSet())


def test_equality_ignores_order():
    assert CustomSet([1, 2, 3]) == CustomSet([3, 2, 1])


def test_different_sets_are_not_equal():
    assert CustomSet([1, 2]) != CustomSet([1, 3])
    assert CustomSet([1]) != CustomSet([1, 2])


def test_empty_sets_are_equal():
    assert CustomSet() == CustomSet()


def test_intersection_keeps_common_elements():
    result = CustomSet([1, 2, 3]).intersection(CustomSet([2, 3, 4]))
    assert result == CustomSet([2, 3])


def test_intersection_of_disjoint_sets_is_empty():
    assert CustomSet([1]).intersection(CustomSet([2])).isempty()


def test_difference_removes_other_elements():
    assert CustomSet([1, 2, 3]) - CustomSet([2, 4]) == CustomSet([1, 3])


def test_difference_with_disjoint_set_is_unchanged():
    assert CustomSet([1, 2]) - CustomSet([3]) == CustomSet([1, 2])


def test_difference_of_set_with_itself_is_empty():
    assert (CustomSet([1, 2]) - CustomSet([1, 2])).isempty()


def test_union_contains_all_elements_once():
    assert CustomSet([1, 2]) + CustomSet([2, 3]) == CustomSet([1, 2, 3])


def test_union_with_empty_set_is_the_other_set():
    assert CustomSet() + CustomSet([1]) == CustomSet([1])


def test_operators_do_not_modify_operands():
    a = CustomSet([1, 2])
    b = CustomSet([2, 3])
    _ = a + b
    _ = a - b
    _ = a.intersection(b)
    assert a == CustomSet([1, 2])
    assert b == CustomSet([2, 3])


def test_instances_do_not_share_state():
    a = CustomSet()
    a.add(1)
    b = CustomSet()
    assert b.isempty()
    assert 1 not in b
