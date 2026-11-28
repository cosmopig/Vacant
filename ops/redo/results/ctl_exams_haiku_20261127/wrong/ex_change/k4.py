def find_fewest_coins(coins, target):
    if target <= 0:
        return []
    best = [None] * (target + 1)
    best[0] = []
    for amount in range(1, target + 1):
        for coin in coins:
            if coin <= amount and best[amount - coin] is not None:
                candidate = best[amount - coin] + [coin]
                if best[amount] is None or len(candidate) < len(best[amount]):
                    best[amount] = candidate
    if best[target] is None:
        raise ValueError("can't make target with given coins")
    return best[target]
