MOD = 1_000_000_007


def minimumPossibleSum(n: int, target: int) -> int:
    first = (target - 1) // 2

    if n <= first:
        return (n * (n + 1) // 2) % MOD

    ans = (first * (first + 1) // 2) % MOD
    remaining = n - first

    if target % 2 == 0:
        ans = (ans + target // 2) % MOD
        remaining -= 1

    if remaining > 0:
        ans = (ans + remaining * target + remaining * (remaining - 1) // 2) % MOD

    return ans
