import math

def countBalancedPermutations(num: str):
    MOD = 10**9 + 7
    n = len(num)
    total_sum = sum(int(d) for d in num)
    
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    counts = [0] * 10
    for d in num:
        counts[int(d)] += 1
        
    n_e = (n + 1) // 2
    n_o = n // 2
    
    # Precompute factorials and their modular inverses
    max_val = max(n, 10) # Just to be safe, but n is up to 80
    fact = [1] * (max_val + 1)
    inv_fact = [1] * (max_val + 1)
    for i in range(2, max_val + 1):
        fact[i] = (fact[i-1] * i) % MOD
        
    inv_fact[max_val] = pow(fact[max_val], MOD - 2, MOD)
    for i in range(max_val - 1, -1, -1):
        inv_fact[i] = (inv_fact[i+1] * (i + 1)) % MOD

    # dp[j][s] is the sum of products of 1 / (k_i! * (c_i - k_i)!)
    # for digits processed so far, where j is total count and s is total sum.
    dp = [[0] * (target_sum + 1) for _ in range(n_e + 1)]
    dp[0][0] = 1
    
    for d in range(10):
        new_dp = [[0] * (target_sum + 1) for _ in range(n_e + 1)]
        c_d = counts[d]
        for j in range(n_e + 1):
            for s in range(target_sum + 1):
                if dp[j][s] == 0:
                    continue
                # How many of digit d to put in even positions
                for k in range(min(c_d, n_e - j) + 1):
                    new_s = s + d * k
                    if new_s <= target_sum:
                        term = (inv_fact[k] * inv_fact[c_d - k]) % MOD
                        new_dp[j+k][new_s] = (new_dp[j+k][new_s] + dp[j][s] * term) % MOD
        dp = new_dp

    ans = (dp[n_e][target_sum] * fact[n_e]) % MOD
    ans = (ans * fact[n_o]) % MOD
    return ans

if __name__ == "__main__":
    import sys
    # For testing purposes, you can add some inputs here.
    pass
