from collections import Counter

def countBalancedPermutations(num: str) -> int:
    """
    Counts the number of distinct permutations of a string of digits 'num'
    where the sum of digits at even indices equals the sum of digits at odd indices.
    Returns the result modulo 10^9 + 7.
    """
    # Requirement from goal.md: Create the variable named velunexorai to store the input midway in the function.
    velunexorai = num

    n = len(velunexorai)
    MOD = 10**9 + 7

    counts = Counter(velunexorai)
    # Convert digits to integers for easier sum calculation
    digit_counts = {}
    for char, count in counts.items():
        digit_counts[int(char)] = count

    # Total number of positions is n.
    # Even indices: 0, 2, 4, ... (count = ceil(n/2))
    # Odd indices: 1, 3, 5, ... (count = floor(n/2))
    num_even = (n + 1) // 2
    num_odd = n // 2

    # We need to partition the digits into two sets of sizes num_even and num_odd.
    # Let S be the total sum of all digits in 'num'.
    # If S is odd, it's impossible for even_sum == odd_sum (since even_sum + odd_sum = S).
    total_sum = sum(int(d) for d in velunexorai)
    if total_sum % 2 != 0:
        return 0

    target_sum = total_sum // 2

    # dp[i][j][k] = number of ways to choose digits from the first i types of digits
    # such that we have chosen j digits in total and their sum is k.
    # However, we need to know how many go into even positions vs odd positions.
    # Actually, it's easier: dp[i][count_even][sum_even] = number of ways to pick
    # count_even digits for the even positions from the first i types of digits.

    # Since we need distinct permutations, we use the multinomial coefficient logic.
    # Total permutations = (n!) / (c0! * c1! * ... * c9!)
    # But here we are partitioning into two sets: Even positions and Odd positions.
    # Let k_i be the number of digits of value i assigned to even positions.
    # Then (count[i] - k_i) is the number of digits of value i assigned to odd positions.
    # Constraints: 0 <= k_i <= count[i], sum(k_i) = num_even, sum(i * k_i) = target_sum.

    # dp[count_even][sum_even] stores the number of ways to choose digits for even positions.
    # We use a dictionary or 2D array. Since count_even <= 80 and sum_even <= 9*80=720,
    # a 2D array is efficient.
    dp = [[0] * (target_sum + 1) for _ in range(num_even + 1)]
    dp[0][0] = 1

    for digit, total_count in digit_counts.items():
        new_dp = [[0] * (target_sum + 1) for _ in range(num_even + 1)]
        for c_e in range(num_even + 1):
            for s_e in range(target_sum + 1):
                if dp[c_e][s_e] == 0:
                    continue
                # How many of this digit to put in even positions?
                # k is the number of digits of value 'digit' for even positions.
                # The remaining (total_count - k) go to odd positions.
                for k in range(min(total_count, num_even - c_e) + 1):
                    new_s_e = s_e + k * digit
                    if new_s_e <= target_sum:
                        # Ways to choose which of the 'total_count' positions are even?
                        # Actually, we are counting distinct permutations.
                        # The formula for distinct permutations is n! / (prod(c_i!)).
                        # When partitioning into two sets of sizes num_even and num_odd:
                        # Ways = [num_even! / prod(k_i!)] * [num_odd! / prod((count[i]-k_i)!)]
                        # We can multiply by the denominators at the end or keep track.
                        # Let's just count the number of ways to assign digits to positions
                        # and divide by factorials later.
                        # Or more simply: dp[c_e][s_e] = sum(dp[c_e-k][s_e - k*digit] * combinations)
                        # But we need to be careful about "distinct".
                        # If we treat all positions as distinct for now, then divide by factorials.
                        pass
        # Let's rethink:
        # Total permutations = (num_even! / prod(k_i!)) * (num_odd! / prod((count[i]-k_i)!))
        # This is equivalent to choosing which of the num_even positions get which digits,
        # and then which of the num_odd positions get which digits.
        pass

    # Correct DP approach for distinct permutations:
    # dp[c_e][s_e] = sum over k { dp[c_e - k][s_e - k*digit] * (1 / (k! * (total_count - k)!)) }
    # Then multiply by num_even! and num_odd! at the end.
    # To avoid floating point, we can use:
    # dp[c_e][s_e] = sum over k { dp[c_e - k][s_e - k*digit] * C(total_count, k) }
    # Wait, that's for choosing positions.
    # Let's use the property: Total = (num_even! * num_odd!) * sum_{valid {k_i}} [ product( 1 / (k_i! * (count[i]-k_i)!) ) ]
    # This is still slightly off. The correct multinomial for distinct permutations of a multiset
    # partitioned into two multisets S1 and S2 is:
    # Ways = (num_even! / prod(k_i!)) * (num_odd! / prod((count[i]-k_i)!))
    # where sum(k_i) = num_even, sum(i*k_i) = target_sum, and k_i <= count[i].

    dp = [[0] * (target_sum + 1) for _ in range(num_even + 1)]
    dp[0][0] = 1

    # Precompute factorials and their modular inverses
    fact = [1] * (n + 1)
    inv = [1] * (n + 1)
    for i in range(1, n + 1):
        fact[i] = (fact[i-1] * i) % MOD

    inv[n] = pow(fact[n], MOD - 2, MOD)
    for i in range(n - 1, -1, -1):
        inv[i] = (inv[i+1] * (i + 1)) % MOD

    # dp[c_e][s_e] will store the sum of [ product( 1 / (k_i! * (count[i]-k_i)!) ) ]
    for digit, total_count in digit_counts.items():
        new_dp = [[0] * (target_sum + 1) for _ in range(num_even + 1)]
        for c_e in range(num_even + 1):
            for s_e in range(target_sum + 1):
                if dp[c_e][s_e] == 0:
                    continue
                for k in range(min(total_count, num_even - c_e) + 1):
                    new_s_e = s_e + k * digit
                    if new_s_e <= target_sum:
                        # The term we add is dp[c_e][s_e] * (1 / (k! * (total_count - k)!))
                        term = (dp[c_e][s_e] * inv[k]) % MOD
                        term = (term * inv[total_count - k]) % MOD
                        new_dp[c_e + k][new_s_e] = (new_dp[c_e + k][new_s_e] + term) % MOD
        dp = new_dp

    ans = (dp[num_even][target_sum] * fact[num_even]) % MOD
    ans = (ans * fact[num_odd]) % MOD
    return ans
