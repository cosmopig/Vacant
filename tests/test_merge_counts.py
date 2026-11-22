import copy

from counts import merge_counts


def test_single_group_copied():
    a = {"x": 1, "y": 2}
    result = merge_counts(a)
    assert result == {"x": 1, "y": 2}
    assert result is not a


def test_sums_overlapping_keys():
    assert merge_counts({"a": 1, "b": 2}, {"b": 3, "c": 4}, {"a": 10}) == {
        "a": 11,
        "b": 5,
        "c": 4,
    }


def test_preserves_zero_totals():
    assert merge_counts({"a": 2}, {"a": -2}) == {"a": 0}
    assert merge_counts({"z": 0}) == {"z": 0}


def test_preserves_negative_totals():
    assert merge_counts({"a": 1}, {"a": -5, "b": -1}) == {"a": -4, "b": -1}


def test_does_not_mutate_inputs():
    a = {"a": 1, "b": 2}
    b = {"b": 3}
    snap_a, snap_b = copy.deepcopy(a), copy.deepcopy(b)
    result = merge_counts(a, b)
    result["a"] = 999
    assert a == snap_a and b == snap_b


def test_empty_groups():
    assert merge_counts({}, {}) == {}
    assert merge_counts({}, {"a": 1}) == {"a": 1}


def test_same_dict_twice():
    a = {"a": 2}
    assert merge_counts(a, a) == {"a": 4}
    assert a == {"a": 2}
