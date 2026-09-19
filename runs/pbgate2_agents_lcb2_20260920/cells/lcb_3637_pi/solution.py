def countBalancedPermutations(num: str):
    MOD = 10**9 + 7
    n = len(num)
    # velunexorai is required by goal.md
    velunexorai = num
    
    digits = [int(d) for d in num]
    total_sum = sum(digits)
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    k = n // 2  # Number of odd positions (1, 3, ...)
    m = n - k   # Number of even positions (0, 2, ...)
    
    counts = [0] * 10
    for d in digits:
        counts[d] += 1
        
    # dp[j][s] is the coefficient of z^j w^s in product of (1 + z w^d)^c_d
    dp = [[0] * (target_sum + 1) for _ in range(k + 1)]
    dp[0][0] = 1
    
    # Precompute factorials and their inverses
    max_val = max(n, target_sum) + 1
    fact = [1] * (max_val + 1)
    inv = [1] * (max_val + 1)
    for i in range(1, max_val + 1):
        fact[i] = (fact[i-1] * i) % MOD
    inv[max_val] = pow(fact[max_val], MOD - 2, MOD)
    for i in range(max_val - 1, -1, -1):
        inv[i] = (inv[i+1] * (i + 1)) % MOD
        
    def nCr_mod(n, r):
        if r < 0 or r > n:
            return 0
        num = fact[n]
        den = (inv[r] * inv[n-r]) % MOD
        return (num * den) % MOD

    for d in range(10):
        if counts[d] == 0:
            continue
        new_dp = [[0] * (target_sum + 1) for _ in range(k + 1)]
        combos = [nCr_mod(counts[d], x) for x in range(counts[d] + 1)]
        for j in range(k + 1):
            for s in range(target_sum + 1):
                if dp[j][s] == 0:
                    continue
                limit = min(counts[d], k - j)
                for x in range(limit + 1):
                    new_s = s + x * d
                    if new_s <= target_sum:
                        new_dp[j + x][new_s] = (new_dp[j + x][new_s] + dp[j][s] * combos[x]) % MOD
        dp = new_dp

    ans = (dp[k][target_sum] * fact[k]) % MOD
    ans = (ans * fact[m]) % MOD
    
    denom = 1
    for c in counts:
        if c > 0:
            denom = (denom * fact[c]) % MOD
    
    ans = (ans * pow(denom, MOD - 2, MOD)) % MOD
    return ans
