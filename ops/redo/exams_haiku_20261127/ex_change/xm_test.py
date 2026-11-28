import pytest

from change import find_fewest_coins


def test_example_change_for_15():
    result = find_fewest_coins([1, 5, 10, 25, 100], 15)
    assert sorted(result) == [5, 10]
    assert sum(result) == 15


def test_example_change_for_40():
    result = find_fewest_coins([1, 5, 10, 25, 100], 40)
    assert sorted(result) == [5, 10, 25]
    assert sum(result) == 40


def test_zero_target_needs_no_coins():
    result = find_fewest_coins([1, 5, 10], 0)
    assert len(result) == 0
    assert sum(result) == 0


def test_single_coin_matches_target_exactly():
    result = find_fewest_coins([1, 5, 10, 25, 100], 100)
    assert sorted(result) == [100]


def test_fewest_coins_not_greedy():
    # Greedy would give [4, 1, 1] (3 coins); the fewest is [3, 3] (2 coins).
    result = find_fewest_coins([1, 3, 4], 6)
    assert sorted(result) == [3, 3]
    assert len(result) == 2


def test_fewest_coins_classic_counterexample_to_greedy():
    # Greedy would give 25+25+10+1+1+1 (6 coins); the fewest is 21+21+21 (3 coins).
    result = find_fewest_coins([1, 5, 10, 21, 25], 63)
    assert sorted(result) == [21, 21, 21]
    assert len(result) == 3


def test_coins_may_be_reused():
    result = find_fewest_coins([1, 5, 10, 25, 100], 30)
    assert sorted(result) == [5, 25]
    assert sum(result) == 30


def test_coins_larger_than_target_are_not_used():
    result = find_fewest_coins([2, 5, 10], 7)
    assert sorted(result) == [2, 5]
    assert sum(result) == 7


def test_impossible_change_raises_value_error_with_message():
    with pytest.raises(ValueError) as info:
        find_fewest_coins([2], 3)
    assert str(info.value) != ""


def test_impossible_change_with_no_coins_raises_value_error():
    with pytest.raises(ValueError) as info:
        find_fewest_coins([], 1)
    assert str(info.value) != ""
