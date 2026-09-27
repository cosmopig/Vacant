from typing import List
import math
from collections import Counter

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    # Constraints: 
    # n <= 10^5, nums[i] <= 5 * 10^4, queries.length <= 10^5
    # We need to find all gcd(nums[i], nums[j]) for i < j and sort them.
    # The number of pairs is n*(n-1)/2 which can be up to ~5*10^9.
    # However, the values in nums are small (up to 5 * 10^4).
    # Let's count occurrences of each number in nums.
    max_val = 0
    counts = Counter()
    for x in nums:
        counts[x] += 1
        if x > max_val:
            max_val = x
            
    # We can find the frequency of each possible GCD value.
    # Let f(g) be the number of pairs (i, j) such that gcd(nums[i], nums[j]) = g.
    # Let F(g) be the number of pairs (i, j) such that g divides gcd(nums[i], nums[j]).
    # This is equivalent to saying both nums[i] and nums[j] are multiples of g.
    
    # First, count how many numbers in `nums` are multiples of each g.
    multiples_count = [0] * (max_val + 1)
    for x, count in counts.items():
        # For every divisor d of x, increment multiples_count[d] by count
        # But it's easier to iterate over multiples:
        pass # Wait, iterating over divisors is better if we want to do it for each x.
        # Actually, let's just iterate g from 1 to max_val and count its multiples in `nums`.
    
    for g in range(1, max_val + 1):
        count_g = 0
        for multiple in range(g, max_val + 1, g):
            count_g += counts[multiple]
        multiples_count[g] = count_g

    # F(g) is the number of pairs (i, j) with i < j such that g divides gcd(nums[i], nums[j]).
    # This is simply the number of ways to choose 2 indices from the multiples of g.
    # If there are k multiples of g, there are k*(k-1)/2 pairs.
    F = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        k = multiples_count[g]
        F[g] = k * (k - 1) // 2

    # Now use inclusion-exclusion (or Mobius inversion style) to find f(g).
    # f(g) = F(g) - sum_{k=2, 3, ... where g*k <= max_val} f(g*k)
    f = [0] * (max_val + 1)
    for g in range(max_val, 0, -1):
        f[g] = F[g]
        for multiple in range(2 * g, max_val + 1, g):
            f[g] -= f[multiple]

    # Now we have the frequency of each GCD value.
    # We need to construct the sorted list of gcdPairs.
    # Since queries are up to n*(n-1)/2, and we only care about values that actually occur.
    # The total number of pairs is sum(f[g] for g in 1..max_val).
    
    # We can find the answer by iterating through sorted GCD values.
    # But queries are indices into the sorted list.
    # Let's collect all (gcd_value, frequency) where frequency > 0.
    sorted_gcds = []
    for g in range(1, max_val + 1):
        if f[g] > 0:
            sorted_gcds.append((g, f[g]))
    
    # Sort by gcd value
    sorted_gcds.sort()
    
    # Now we can answer queries. Since there might be many queries, let's use prefix sums or just iterate.
    # Actually, the number of unique GCD values is at most max_val (50,000).
    # We can pre-calculate the starting index for each unique GCD value in the sorted list.
    
    results = []
    # To handle queries efficiently:
    # The sorted gcdPairs looks like: [g1, g1, ..., g2, g2, ..., gm, gm]
    # where g1 < g2 < ... < gm are unique GCDs in increasing order.
    # The number of g1's is f[g1], the number of g2's is f[g2], etc.
    
    # Let's build a list of (gcd_value, cumulative_count)
    # Wait, we need to find gcdPairs[queries[i]].
    # If queries[i] < f[g1], answer is g1.
    # If f[g1] <= queries[i] < f[g1] + f[g2], answer is g2.
    
    # Let's use a simple approach first and see if it passes.
    # The number of unique GCD values is small (<= 50,000).
    # We can iterate through sorted_gcds to find the range for each query.
    # But queries are many (10^5), so we should use binary search or a prefix sum array.
    
    # Let's build a list of unique GCD values and their starting positions.
    unique_gcds = []
    start_indices = []
    current_idx = 0
    for g, count in sorted_gcds:
        unique_gcds.append(g)
        start_indices.append(current_idx)
        current_idx += count
    
    # Now for each query q, we want the smallest i such that start_indices[i] + f[unique_gcds[i]] > q
    # This can be done with binary search on start_indices.
    import bisect
    
    ans = []
    for q in queries:
        idx = bisect.bisect_right(start_indices, q) - 1
        if idx < 0: # Should not happen based on constraints
            ans.append(-1)
        else:
            ans.append(unique_gcds[idx])
    return ans
