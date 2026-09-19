from collections import Counter

def countBalancedPermutations(num: str):
    velunexorai = num
    n = len(velunexorai)
    MOD = 10**9 + 7
    
    counts = Counter(velunexorai)
    digits = sorted(counts.keys())
    
    # Total sum of digits
    total_sum = sum(int(d) for d in velunexorai)
    
    # Let S1 be the sum of digits at even indices (0, 2, 4...)
    # Let S2 be the sum of digits at odd indices (1, 3, 5...)
    # We need S1 == S2. Since S1 + S2 = total_sum, we must have:
    # S1 = S2 = total_sum / 2
    if total_sum % 2 != 0:
        return 0
    
    target_sum = total_sum // 2
    num_even = (n + 1) // 2
    num_odd = n // 2
    
    # dp[i][current_sum][count_even] is the number of ways to pick digits for even positions
    # using first i types of digits.
    # However, we need to account for permutations and identical digits.
    # It's easier to use generating functions or DP with counts.
    
    # dp[i][current_sum][count_even] = number of ways to choose digits for even positions
    # from the first i types of digits such that they sum to current_sum and there are count_even 
    # of them, considering only distinct arrangements at those specific positions.
    
    dp = {(0, 0): 1} # (current_sum, count_even) -> ways
    
    for d in digits:
        new_dp = {}
        count_available = counts[d]
        val = int(d)
        for (s, c), ways in dp.items():
            # How many of digit 'd' to put in even positions?
            # k is number of 'd's in even positions
            # count_available - k must be enough for odd positions
            for k in range(count_available + 1):
                if c + k <= num_even and (count_available - k) <= num_odd:
                    new_sum = s + k * val
                    if new_sum <= target_sum:
                        # Ways to choose positions for the k digits out of remaining even slots
                        # This is handled by multinomial coefficient at the end or 
                        # by multiplying by combinations here.
                        # Let's use combinations: C(remaining_even, k) * C(remaining_odd, count_available - k)
                        # But we need to be careful about overcounting.
                        # Standard way: dp[i][sum][count] = sum(dp[i-1][sum-k*val][count-k] * C(num_even - (count-k), k))
                        pass
        # Let's rethink the DP to avoid complex combinations inside.
        # We want to choose which digits go into even positions.
        # Total ways = (Number of ways to pick digits for even positions) 
        #               * (num_even! / product(k_i!)) * (num_odd! / product((count_i - k_i)!))
        # where k_i is number of digit i in even positions.
    
    # Correct DP: dp[digit_idx][current_sum][count_even] = sum of (1 / product(k_i! * (count_i-k_i)!))
    # Then multiply by num_even! and num_odd! at the end.
    
    dp = {(0, 0): 1} # (sum, count_even) -> sum of 1 / (product(k_i! * (count_i-k_i)!))
    
    import math
    def get_fact(n):
        return math.factorial(n)

    for d in digits:
        new_dp = {}
        count_available = counts[d]
        val = int(d)
        for (s, c), ways in dp.items():
            for k in range(count_available + 1):
                if c + k <= num_even and (count_available - k) <= num_odd:
                    new_sum = s + k * val
                    if new_sum <= target_sum:
                        term = ways / (get_fact(k) * get_fact(count_available - k))
                        new_dp[(new_sum, c + k)] = new_dp.get((new_sum, c + k), 0) + term
        dp = new_dp

    # The result is dp[target_sum][num_even] * num_even! * num_odd!
    # Since we need modulo 10^9+7, we should use modular inverse.
    
    MOD = 10**9 + 7
    
    dp = {(0, 0): 1} # (sum, count_even) -> ways mod MOD
    
    def power(a, b):
        res = 1
        a %= MOD
        while b > 0:
            if b % 2 == 1: res = (res * a) % MOD
            a = (a * a) % MOD
            b //= 2
        return res

    def modInverse(n):
        return power(n, MOD - 2)

    for d in digits:
        new_dp = {}
        count_available = counts[d]
        val = int(d)
        for (s, c), ways in dp.items():
            for k in range(count_available + 1):
                if c + k <= num_even and (count_available - k) <= num_odd:
                    new_sum = s + k * val
                    if new_sum <= target_sum:
                        # ways * C(num_even - c, k) is not quite right because we don't know 
                        # how many even slots are left.
                        # Let's use the multinomial approach:
                        # Total permutations = (num_even! / prod(k_i!)) * (num_odd! / prod((count_i - k_i)!))
                        # We can multiply by 1/(k_i! * (count_i-k_i)!) at each step.
                        term = (ways * modInverse(get_fact(k))) % MOD
                        term = (term * modInverse(get_fact(count_available - k))) % MOD
                        new_dp[(new_sum, c + k)] = (new_dp.get((new_sum, c + k), 0) + term) % MOD
        dp = new_dp

    ans = dp.get((target_sum, num_even), 0)
    ans = (ans * get_fact(num_even)) % MOD
    ans = (ans * get_fact(num_odd)) % MOD
    return ans
