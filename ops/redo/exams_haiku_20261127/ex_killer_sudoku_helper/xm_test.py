from killer_sudoku_helper import combinations


def _normalized(result):
    return [list(combo) for combo in result]


def test_single_combination_three_digits_sum_seven():
    assert _normalized(combinations(7, 3, [])) == [[1, 2, 4]]


def test_two_digits_sum_ten_lists_all_pairs_in_order():
    assert _normalized(combinations(10, 2, [])) == [
        [1, 9],
        [2, 8],
        [3, 7],
        [4, 6],
    ]


def test_excluded_digits_remove_matching_combinations():
    assert _normalized(combinations(10, 2, [1, 4])) == [[2, 8], [3, 7]]


def test_three_digits_sum_ten_all_combinations_sorted():
    assert _normalized(combinations(10, 3, [])) == [
        [1, 2, 7],
        [1, 3, 6],
        [1, 4, 5],
        [2, 3, 5],
    ]


def test_repeated_digit_pair_is_not_allowed():
    # 2 + 2 = 4 would repeat a digit, so only 1 + 3 is valid.
    assert _normalized(combinations(4, 2, [])) == [[1, 3]]


def test_digit_cannot_repeat_in_cage_sum_three():
    assert _normalized(combinations(3, 2, [])) == [[1, 2]]


def test_single_cell_cage_gives_the_digit_itself():
    assert _normalized(combinations(5, 1, [])) == [[5]]


def test_single_cell_cage_excluded_digit_gives_no_combinations():
    assert _normalized(combinations(3, 1, [3])) == []


def test_impossible_sum_for_size_gives_empty_result():
    # Smallest possible sum of two distinct digits is 1 + 2 = 3.
    assert _normalized(combinations(2, 2, [])) == []


def test_largest_pair_sum_has_single_combination():
    assert _normalized(combinations(17, 2, [])) == [[8, 9]]


def test_excluding_all_but_one_digit_leaves_no_pair():
    assert _normalized(combinations(10, 2, [1, 2, 3, 4, 5, 6, 7, 8])) == []


def test_full_nine_cell_cage_uses_every_digit_once():
    assert _normalized(combinations(45, 9, [])) == [[1, 2, 3, 4, 5, 6, 7, 8, 9]]


def test_three_digit_cage_sum_six_has_single_combination():
    assert _normalized(combinations(6, 3, [])) == [[1, 2, 3]]
