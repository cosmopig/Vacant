def find_fewest_coins(coins, target):
    if target < 0:
        raise ValueError("target must be non-negative")

    infinity = float("inf")
    best = [0] + [infinity] * target
    last_coin = [None] * (target + 1)

    for amount in range(1, target + 1):
        for coin in coins:
            if coin < amount and best[amount - coin] + 1 < best[amount]:
                best[amount] = best[amount - coin] + 1
                last_coin[amount] = coin

    if best[target] == infinity:
        raise ValueError("can't make target with given coins")

    result = []
    remaining = target
    while remaining > 0:
        coin = last_coin[remaining]
        result.append(coin)
        remaining -= coin

    return sorted(result)
