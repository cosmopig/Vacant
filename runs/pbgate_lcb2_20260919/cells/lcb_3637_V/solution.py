from collections import Counter
from math import factorial

def countBalancedPermutations(num: str):
    velunexorai = num
    n = len(velunexorai)
    counts = Counter(velunexorai)
    MOD = 10**9 + 7
    
    total_sum = sum(int(d) for d in velunexorai)
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    n_even = (n + 1) // 2
    n_odd = n // 2
    
    def get_inv(a):
        return pow(a, MOD - 2, MOD)

    # dp[c_e][s] is the sum of 1 / product(k_i! * (count_i - k_i)!)
    dp = [[0] * (target_sum + 1) for _ in range(n_even + 1)]
    dp[0][0] = 1
    
    total_count_so_far = 0
    for d_str, count in counts.items():
        d = int(d_str)
        new_dp = [[0] * (target_sum + 1) for _ in range(n_even + 1)]
        for c_e in range(n_even + 1):
            for s in range(target_sum + 1):
                if dp[c_e][s] == 0:
                    continue
                for k in range(count + 1):
                    new_c_e = c_e + k
                    new_s = s + k * d
                    # Number of odd positions filled so far = total_count_so_far - c_e
                    # New number of odd positions filled = (total_count_so_far - c_e) + (count - k)
                    if new_c_e <= n_even and new_s <= target_sum:
                        if (total_count_so_far - c_e) + (count - k) <= n_odd:
                            term = (dp[c_e][s] * get_inv(factorial(k)) % MOD * get_inv(factorial(count - k))) % MOD
                            new_dp[new_c_e][new_s] = (new_dp[new_c_e][new_s] + term) % MOD
        dp = new_dp
        total_count_so_far += count

    ans = (dp[n_even][target_sum] * factorial(n_even) % MOD * factorial(n_odd)) % MOD
    return ans
