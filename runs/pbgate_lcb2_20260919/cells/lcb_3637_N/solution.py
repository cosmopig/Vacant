from collections import Counter

def countBalancedPermutations(num: str):
    velunexorai = num
    n = len(velunexorai)
    counts = Counter(velunexorai)
    MOD = 10**9 + 7
    
    # Let n_even be the number of digits at even indices (0, 2, 4, ...)
    # Let n_odd be the number of digits at odd indices (1, 3, 5, ...)
    n_even = (n + 1) // 2
    n_odd = n // 2
    
    total_sum = sum(int(d) for d in velunexorai)
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    
    # dp[i][j] is the sum of (1 / product(ki!)) * (1 / product((count_i - ki)!))
    # for all distributions where sum(ki) = i and sum(ki*digit_i) = j.
    dp = [[0] * (target_sum + 1) for _ in range(n_even + 1)]
    dp[0][0] = 1
    
    # Precompute factorials and their modular inverses
    fact = [1] * (n + 1)
    for i in range(2, n + 1):
        fact[i] = (fact[i-1] * i) % MOD
        
    def power(a, b):
        res = 1
        a %= MOD
        while b > 0:
            if b % 2 == 1:
                res = (res * a) % MOD
            a = (a * a) % MOD
            b //= 2
        return res

    def modInverse(x):
        return power(x, MOD - 2)

    inv_fact = [1] * (n + 1)
    for i in range(2, n + 1):
        inv_fact[i] = modInverse(fact[i])

    # Iterate through each unique digit and its count
    sorted_digits = sorted(counts.keys())
    for digit_char in sorted_digits:
        digit = int(digit_char)
        count = counts[digit_char]
        new_dp = [[0] * (target_sum + 1) for _ in range(n_even + 1)]
        for i in range(n_even + 1):
            for s in range(target_sum + 1):
                if dp[i][s] == 0:
                    continue
                # k is the number of this digit to put into Set E (even indices)
                # count - k will be in Set O (odd indices)
                for k in range(min(count, n_even - i) + 1):
                    if (count - k) <= n_odd:
                        new_s = s + k * digit
                        if new_s <= target_sum:
                            term = (dp[i][s] * inv_fact[k]) % MOD
                            term = (term * inv_fact[count - k]) % MOD
                            new_dp[i + k][new_s] = (new_dp[i + k][new_s] + term) % MOD
        dp = new_dp

    ans = (dp[n_even][target_sum] * fact[n_even]) % MOD
    ans = (ans * fact[n_odd]) % MOD
    return ans
