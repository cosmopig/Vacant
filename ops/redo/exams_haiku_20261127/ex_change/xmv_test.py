import pytest

from change import find_fewest_coins

US_COINS = [1, 5, 10, 25, 100]


def test_example_15_uses_one_five_and_one_ten():
    # SRC: "An amount of 15 with available coin values [1, 5, 10, 25, 100] should return one coin of value 5 and one coin of value 10, or [5, 10]."
    assert sorted(find_fewest_coins(US_COINS, 15)) == [5, 10]


def test_example_40_uses_five_ten_and_twenty_five():
    # SRC: "An amount of 40 with available coin values [1, 5, 10, 25, 100] should return one coin of value 5, one coin of value 10, and one coin of value 25, or [5, 10, 25]."
    assert sorted(find_fewest_coins(US_COINS, 40)) == [5, 10, 25]


def test_exact_coin_value_gives_single_coin():
    # SRC: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change."
    assert sorted(find_fewest_coins(US_COINS, 100)) == [100]


def test_zero_change_gives_no_coins():
    # SRC: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change."
    assert find_fewest_coins(US_COINS, 0) == []


def test_fewest_coins_is_not_always_greedy():
    # SRC: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change."
    assert sorted(find_fewest_coins([1, 3, 4], 6)) == [3, 3]


def test_result_sum_equals_target_for_larger_amount():
    # SRC: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change."
    assert sum(find_fewest_coins(US_COINS, 99)) == 99


def test_result_uses_fewest_coins_for_larger_amount():
    # SRC: "Determine the fewest number of coins to give a customer so that the sum of their values equals the correct amount of change."
    assert len(find_fewest_coins(US_COINS, 99)) == 9


def test_impossible_change_raises_value_error():
    # SRC: "This particular exercise requires that you use the [raise statement](https://docs.python.org/3/reference/simple_stmts.html#the-raise-statement) to "throw" a `ValueError` when change cannot be made with the coins given."
    with pytest.raises(ValueError):
        find_fewest_coins([2], 3)


def test_impossible_change_error_has_message():
    # SRC: "This particular exercise requires that you use the [raise statement](https://docs.python.org/3/reference/simple_stmts.html#the-raise-statement) to "throw" a `ValueError` when change cannot be made with the coins given."
    with pytest.raises(ValueError) as info:
        find_fewest_coins([5, 10], 7)
    message = str(info.value)
    # SRC: "When you do this, you should always include a **meaningful error message** to indicate what the source of the error is."
    assert message.strip() != ""
