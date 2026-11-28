from sublist import sublist, SUBLIST, SUPERLIST, EQUAL, UNEQUAL


def test_equal_lists():
    # SRC: "If `A = []` and `B = []` (both lists are empty), then `A` and `B` are equal"
    assert sublist([], []) == EQUAL
    # SRC: "If `A = [1, 2, 3]` and `B = [1, 2, 3]`, then `A` and `B` are equal"
    assert sublist([1, 2, 3], [1, 2, 3]) == EQUAL
    pass  # deleted by xmv_post: quote_not_in_text


def test_superlist():
    # SRC: "If `A = [1, 2, 3]` and `B = []`, then `A` is a superlist of `B`"
    assert sublist([1, 2, 3], []) == SUPERLIST
    # SRC: "If `A = [1, 2, 3, 4, 5]` and `B = [2, 3, 4]`, then `A` is a superlist of `B`"
    assert sublist([1, 2, 3, 4, 5], [2, 3, 4]) == SUPERLIST
    # SRC: "List `A` is a superlist of `B` if `A` contains a contiguous sub-sequence of values equal to `B`."
    assert sublist([1, 2, 3], [3]) == SUPERLIST


def test_sublist():
    # SRC: "If `A = []` and `B = [1, 2, 3]`, then `A` is a sublist of `B`"
    assert sublist([], [1, 2, 3]) == SUBLIST
    # SRC: "If `A = [1, 2, 3]` and `B = [1, 2, 3, 4, 5]`, then `A` is a sublist of `B`"
    assert sublist([1, 2, 3], [1, 2, 3, 4, 5]) == SUBLIST
    # SRC: "If `A = [3, 4, 5]` and `B = [1, 2, 3, 4, 5]`, then `A` is a sublist of `B`"
    assert sublist([3, 4, 5], [1, 2, 3, 4, 5]) == SUBLIST
    # SRC: "If `A = [3, 4]` and `B = [1, 2, 3, 4, 5]`, then `A` is a sublist of `B`"
    assert sublist([3, 4], [1, 2, 3, 4, 5]) == SUBLIST


def test_unequal_lists():
    # SRC: "If `A = [1, 2, 4]` and `B = [1, 2, 3, 4, 5]`, then `A` and `B` are unequal"
    assert sublist([1, 2, 4], [1, 2, 3, 4, 5]) == UNEQUAL
    # SRC: "If `A = [1, 2, 3]` and `B = [1, 3, 2]`, then `A` and `B` are unequal"
    assert sublist([1, 2, 3], [1, 3, 2]) == UNEQUAL
