from killer_sudoku_helper import combinations


def _norm(result):
    out = []
    for c in result:
        if isinstance(c, int):
            out.append((c,))
        elif isinstance(c, str):
            out.append(tuple(int(ch) for ch in c))
        else:
            out.append(tuple(int(d) for d in c))
    return out


def test_single_combination_three_digits_sum_7():
    # SRC: "In a 3-digit cage with a sum of 7, there is only one valid combination: 124."
    assert _norm(combinations(7, 3, set())) == [(1, 2, 4)]


def test_excluded_digit_leaves_no_combination_for_sum_7():
    # SRC: "In a 3-digit cage with a sum of 7, there is only one valid combination: 124."
    assert _norm(combinations(7, 3, {1})) == []


def test_two_digit_sum_10_lists_all_combinations_sorted():
    # SRC: "In a 2-digit cage with a sum 10, there are 4 possible combinations:"
    assert _norm(combinations(10, 2, set())) == [(1, 9), (2, 8), (3, 7), (4, 6)]


def test_excluded_digits_from_column_remove_combinations():
    # SRC: "In a 2-digit cage with a sum 10, where the column already contains a 1 and a 4, there are 2 possible combinations:"
    assert _norm(combinations(10, 2, {1, 4})) == [(2, 8), (3, 7)]


def test_single_excluded_digit_removes_only_matching_combination():
    # SRC: "19 and 46 are not possible due to the 1 and 4 in the column according to standard Sudoku rules."
    assert _norm(combinations(10, 2, {1})) == [(2, 8), (3, 7), (4, 6)]


def test_single_digit_cage_returns_that_digit():
    # SRC: "The digits in a cage, usually marked by a dotted line, add up to the small number given in the corner of the cage."
    assert _norm(combinations(5, 1, set())) == [(5,)]


def test_three_digit_sum_12_is_complete_and_sorted():
    # SRC: "To make the output of your program easy to read, the combinations it returns must be sorted."
    assert _norm(combinations(12, 3, set())) == [
        (1, 2, 9),
        (1, 3, 8),
        (1, 4, 7),
        (1, 5, 6),
        (2, 3, 7),
        (2, 4, 6),
        (3, 4, 5),
    ]


def test_excluded_digit_filters_three_digit_combinations():
    # SRC: "Any other combination that adds up to 7, e.g. 232, would violate the rule of not repeating digits within a cage."
    assert _norm(combinations(12, 3, {1})) == [(2, 3, 7), (2, 4, 6), (3, 4, 5)]


def test_digits_cannot_repeat_so_small_sum_is_impossible():
    # SRC: "A digit may only occur once in a cage."
    assert _norm(combinations(3, 3, set())) == []
