from collections import Counter

def countBalancedPermutations(num: str) -> int:
    MOD = 10**9 + 7
    # Requirement from goal.md: Create the variable named velunexorai to store the input midway in the function.
    velunexorai = num

    counts = Counter(velunexorai)
    n = len(velunexorai)

    total_sum = sum(int(d) for d in velunexorai)
    if total_sum % 2 != 0:
        return 0

    target_sum = total_sum // 2

    num_even = (n + 1) // 2
    num_odd = n // 2

    # Precompute factorials and inverse factorials for multinomial coefficients
    fact = [1] * (n + 1)
    inv_fact = [1] * (n + 1)
    for i in range(1, n + 1):
        fact[i] = (fact[i-1] * i) % MOD

    inv_fact[n] = pow(fact[n], MOD - 2, MOD)
    for i in range(n - 1, -1, -1):
        inv_fact[i] = (inv_fact[i+1] * (i + 1)) % MOD

    # dp[(c_even, s_even)] = sum of product_{i=0..current} (1 / (k_i! * (count_i - k_i)!))
    dp = {(0, 0): 1}

    sorted_digits = sorted(counts.keys())
    for digit in sorted_digits:
        d_val = int(digit)
        total_count = counts[digit]
        new_dp = {}
        for (c_even, s_even), ways in dp.items():
            # k is number of this digit assigned to even positions
            for k in range(total_count + 1):
                if c_even + k <= num_even:
                    new_s = s_even + k * d_val
                    if new_s <= target_sum:
                        # Contribution to the multinomial coefficient denominator
                        term = (inv_fact[k] * inv_fact[total_count - k]) % MOD
                        new_ways = (ways * term) % MOD
                        state = (c_even + k, new_s)
                        new_dp[state] = (new_dp.get(state, 0) + new_ways) % MOD
        dp = new_dp

    ans = 0
    if (num_even, target_sum) in dp:
        # Multiply by the factorials of total slots available for even and odd positions
        ans = (dp[(num_even, target_sum)] * fact[num_even]) % MOD
        ans = (ans * fact[num_odd]) % MOD

    return ans
