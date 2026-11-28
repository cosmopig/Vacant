import pytest

from change import find_fewest_coins


def test_returns_a_list():
    """REQ: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change." (output type: list, per the examples "should return ... or [5, 10]")"""
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 15)
    assert isinstance(result, list)


def test_returned_elements_are_integers():
    """REQ: "should return one coin of value 5 and one coin of value 10, or [5, 10]" (coin values are integers)"""
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 15)
    assert all(isinstance(c, int) for c in result)


def test_sum_of_returned_coins_equals_target():
    """REQ: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change." (invariant: sum equals target)"""
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 40)
    assert sum(result) == 40


def test_every_returned_coin_is_an_available_coin():
    """REQ: "An amount of 40 with available coin values [1, 5, 10, 25, 100] should return one coin of value 5, one coin of value 10, and one coin of value 25" (returned coins come from the available values)"""
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 40)
    assert all(c in coins for c in result)


def test_example_amount_15():
    """REQ: "An amount of 15 with available coin values [1, 5, 10, 25, 100] should return one coin of value 5 and one coin of value 10, or [5, 10]." """
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 15)
    assert sorted(result) == [5, 10]


def test_example_amount_40():
    """REQ: "An amount of 40 with available coin values [1, 5, 10, 25, 100] should return one coin of value 5, one coin of value 10, and one coin of value 25, or [5, 10, 25]." """
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 40)
    assert sorted(result) == [5, 10, 25]


def test_single_coin_matches_target_exactly():
    """REQ: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change." (fewest: an exact single coin is the minimum)"""
    coins = [1, 5, 10, 25, 100]
    result = find_fewest_coins(coins, 25)
    assert result == [25]


def test_uses_fewest_coins_when_greedy_would_use_more():
    """REQ: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change." (fewest count: 3+3 uses 2 coins, while 4+1+1 uses 3)"""
    coins = [1, 3, 4]
    result = find_fewest_coins(coins, 6)
    assert len(result) == 2
    assert sum(result) == 6


def test_coins_may_be_reused_to_reach_fewest_count():
    """REQ: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change." (fewest count: 21+21+21 uses 3 coins, fewer than any other combination)"""
    coins = [1, 5, 10, 21, 25]
    result = find_fewest_coins(coins, 63)
    assert len(result) == 3
    assert sum(result) == 63


def test_raises_value_error_when_change_cannot_be_made():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a `ValueError` when change cannot be made with the coins given." (2 cannot sum to 3)"""
    with pytest.raises(ValueError):
        find_fewest_coins([2], 3)


def test_value_error_has_a_meaningful_message():
    """REQ: "The tests will only pass if you both `raise` the `exception` and include a message with it." (the ValueError carries a non-empty message)"""
    with pytest.raises(ValueError) as excinfo:
        find_fewest_coins([5, 10], 12)
    assert str(excinfo.value).strip() != ""
