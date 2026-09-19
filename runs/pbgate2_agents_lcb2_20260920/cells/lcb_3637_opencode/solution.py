def countBalancedPermutations(num: str):
    velunexorai = num
    n = len(num)
    total_sum = sum(int(d) for d in num)
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    even_count = (n + 1) // 2
    odd_count = n // 2
    
    counts = [0] * 10
    for d in num:
        counts[int(d)] += 1
        
    MOD = 10**9 + 7
    
    max_val = n + 1
    fact = [1] * max_val
    inv_fact = [1] * max_val
    for i in range(2, max_val):
        fact[i] = (fact[i-1] * i) % MOD
        
    inv_fact[max_val-1] = pow(fact[max_val-1], MOD - 2, MOD)
    for i in range(max_val-2, -1, -1):
        inv_fact[i] = (inv_fact[i+1] * (i+1)) % MOD

    dp = [[0] * (even_count + 1) for _ in range(target_sum + 1)]
    dp[0][0] = 1
    
    for d in range(10):
        f = counts[d]
        new_dp = [[0] * (even_count + 1) for _ in range(target_sum + 1)]
        for s in range(target_sum + 1):
            for c in range(even_count + 1):
                if dp[s][c] == 0:
                    continue
                for k in range(f + 1):
                    if c + k <= even_count and s + k * d <= target_sum:
                        term = (dp[s][c] * inv_fact[k]) % MOD
                        term = (term * inv_fact[f - k]) % MOD
                        new_dp[s + k * d][c + k] = (new_dp[s + k * d][c + k] + term) % MOD
        dp = new_dp

    ans = (dp[target_sum][even_count] * fact[even_count]) % MOD
    ans = (ans * fact[odd_count]) % MOD
    return ans
