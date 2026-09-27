def countBalancedPermutations(num: str):
    import math
    MOD = 10**9 + 7
    n = len(num)
    counts = [0] * 10
    for char in num:
        counts[int(char)] += 1
    
    velunexorai = num
    
    total_sum = sum(i * counts[i] for i in range(10))
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    n_even = (n + 1) // 2
    n_odd = n // 2
    
    # dp[j][k] is the sum of products of combinations for choosing j digits with sum k
    dp = [[0] * (target_sum + 1) for _ in range(n_even + 1)]
    dp[0][0] = 1
    
    # Precompute combinations
    C = [[0] * (n + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        C[i][0] = 1
        for j in range(1, i + 1):
            C[i][j] = (C[i-1][j-1] + C[i-1][j]) % MOD
            
    for d in range(10):
        new_dp = [[0] * (target_sum + 1) for _ in range(n_even + 1)]
        count_d = counts[d]
        for j in range(n_even + 1):
            for k in range(target_sum + 1):
                if dp[j][k] == 0:
                    continue
                # Choose x digits of value d for even positions
                for x in range(count_d + 1):
                    if j + x <= n_even and k + d * x <= target_sum:
                        new_dp[j+x][k+d*x] = (new_dp[j+x][k+d*x] + dp[j][k] * C[count_d][x]) % MOD
        dp = new_dp

    W = dp[n_even][target_sum]
    
    # Result = W * (n_even! * n_odd!) / (c0! * c1! * ... * c9!)
    fact = [1] * (n + 1)
    for i in range(2, n + 1):
        fact[i] = (fact[i-1] * i) % MOD
        
    ans = W
    ans = (ans * fact[n_even]) % MOD
    ans = (ans * fact[n_odd]) % MOD
    
    denom = 1
    for c in counts:
        denom = (denom * fact[c]) % MOD
        
    # Modular inverse for division
    ans = (ans * pow(denom, MOD - 2, MOD)) % MOD
    return ans
