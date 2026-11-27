def find_fewest_coins(coins, target):
    if target < 0:
        raise ValueError("target must be non-negative")
    result = []
    remaining = target
    for coin in sorted(coins, reverse=True):
        while coin > 0 and coin <= remaining:
            result.append(coin)
            remaining -= coin
    if remaining != 0:
        raise ValueError("can't make target with given coins")
    return sorted(result)
