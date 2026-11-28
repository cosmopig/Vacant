"""Acceptance tests for killer_sudoku_helper.combinations(target, size, exclude)."""
import itertools

from killer_sudoku_helper import combinations


def test_result_is_list_of_digit_sequences():
    """REQ: "a small program that lists all valid combinations for a given cage"."""
    result = combinations(10, 2, [])
    assert isinstance(result, list)
    for combo in result:
        assert isinstance(combo, (list, tuple))
        for digit in combo:
            assert isinstance(digit, int) and not isinstance(digit, bool)


def test_combination_digits_are_standard_sudoku_digits():
    """REQ: "Standard Sudoku rules apply."."""
    for target, size in [(10, 2), (15, 3), (30, 5), (45, 9)]:
        for combo in combinations(target, size, []):
            for digit in combo:
                assert 1 <= digit <= 9


def test_example_1_single_combination():
    """REQ: "In a 3-digit cage with a sum of 7, there is only one valid combination: 124."."""
    assert [list(c) for c in combinations(7, 3, [])] == [[1, 2, 4]]


def test_example_2_four_combinations():
    """REQ: "In a 2-digit cage with a sum 10, there are 4 possible combinations: 19, 28, 37, 46"."""
    assert [list(c) for c in combinations(10, 2, [])] == [
        [1, 9],
        [2, 8],
        [3, 7],
        [4, 6],
    ]


def test_example_3_excluded_digits_restrict_combinations():
    """REQ: "19 and 46 are not possible due to the 1 and 4 in the column according to standard Sudoku rules."."""
    assert [list(c) for c in combinations(10, 2, [1, 4])] == [[2, 8], [3, 7]]


def test_each_combination_has_exactly_size_digits():
    """REQ: "In a 3-digit cage with a sum of 7, there is only one valid combination: 124."."""
    for target, size, exclude in [(15, 3, []), (20, 4, []), (12, 3, [2, 5]), (30, 5, [1, 9])]:
        for combo in combinations(target, size, exclude):
            assert len(combo) == size


def test_each_combination_sums_to_target():
    """REQ: "The digits in a cage, usually marked by a dotted line, add up to the small number given in the corner of the cage."."""
    for target, size, exclude in [(15, 3, []), (20, 4, []), (12, 3, [2, 5]), (30, 5, [1, 9])]:
        for combo in combinations(target, size, exclude):
            assert sum(combo) == target


def test_digits_within_a_combination_are_distinct():
    """REQ: "A digit may only occur once in a cage."."""
    for target, size, exclude in [(15, 3, []), (20, 4, []), (12, 3, [2, 5]), (30, 5, [1, 9])]:
        for combo in combinations(target, size, exclude):
            assert len(set(combo)) == len(combo)


def test_excluded_digits_never_appear_in_any_combination():
    """REQ: "19 and 46 are not possible due to the 1 and 4 in the column according to standard Sudoku rules."."""
    exclude = [1, 4, 9]
    for combo in combinations(15, 3, exclude):
        assert not set(combo) & set(exclude)


def test_outer_list_is_sorted():
    """REQ: "To make the output of your program easy to read, the combinations it returns must be sorted."."""
    for target, size, exclude in [(10, 2, []), (15, 3, []), (20, 4, []), (12, 3, [2, 5])]:
        result = [list(c) for c in combinations(target, size, exclude)]
        assert result == sorted(result)


def test_digits_within_each_combination_are_ascending():
    """REQ: "the combinations it returns must be sorted." (example: "124")."""
    for target, size, exclude in [(15, 3, []), (20, 4, []), (12, 3, [2, 5]), (30, 5, [1, 9])]:
        for combo in combinations(target, size, exclude):
            values = list(combo)
            assert all(a < b for a, b in zip(values, values[1:]))


def test_no_combination_is_listed_twice():
    """REQ: "lists all valid combinations for a given cage"."""
    result = [tuple(c) for c in combinations(15, 3, [])]
    assert len(result) == len(set(result))


def test_impossible_cage_returns_empty_list():
    """REQ: "A digit may only occur once in a cage."."""
    # Smallest possible sum of three distinct digits is 1 + 2 + 3 = 6.
    assert list(combinations(2, 3, [])) == []


def test_single_digit_cage_boundaries():
    """REQ: "The digits in a cage, usually marked by a dotted line, add up to the small number given in the corner of the cage."."""
    assert [list(c) for c in combinations(9, 1, [])] == [[9]]
    assert list(combinations(10, 1, [])) == []


def test_largest_two_digit_cage():
    """REQ: "A digit may only occur once in a cage."."""
    # 17 = 8 + 9 is the only pair of distinct digits reaching the maximum sum.
    assert [list(c) for c in combinations(17, 2, [])] == [[8, 9]]


def test_full_nine_digit_cage():
    """REQ: "The digits in a cage, usually marked by a dotted line, add up to the small number given in the corner of the cage."."""
    # 1 + 2 + ... + 9 = 45 is the only way to use nine distinct digits.
    assert [list(c) for c in combinations(45, 9, [])] == [list(range(1, 10))]


def test_all_candidates_excluded_returns_empty_list():
    """REQ: "19 and 46 are not possible due to the 1 and 4 in the column according to standard Sudoku rules."."""
    # Only digit 5 remains, so no two distinct digits are available.
    assert list(combinations(10, 2, [1, 2, 3, 4, 6, 7, 8, 9])) == []


def test_result_is_complete_against_rule_based_enumeration():
    """REQ: "lists all valid combinations for a given cage"."""
    cases = [
        (10, 2, []),
        (7, 3, []),
        (15, 3, []),
        (12, 3, [2, 5]),
        (20, 4, [1, 9]),
        (30, 5, []),
    ]
    for target, size, exclude in cases:
        expected = [
            list(c)
            for c in itertools.combinations(range(1, 10), size)
            if sum(c) == target and not set(c) & set(exclude)
        ]
        result = [list(c) for c in combinations(target, size, exclude)]
        assert result == expected
