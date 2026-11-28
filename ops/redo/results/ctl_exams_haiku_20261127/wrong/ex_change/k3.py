def find_fewest_coins(coins, target):
    if target < 0:
        raise ValueError("target must be non-negative")

    best = [None] * (target + 1)
    best[0] = []

    for amount in range(1, target + 1):
        for coin in coins:
            if coin <= 0 or coin > amount:
                continue
            previous = best[amount - coin]
            if previous is None:
                continue
            candidate = previous + [coin]
            if best[amount] is None or len(candidate) < len(best[amount]):
                best[amount] = candidate

    if best[target] is None:
        raise ValueError("can't make target with given coins")

    return sorted(best[target], reverse=True)
