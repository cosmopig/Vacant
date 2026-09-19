from typing import List
import math
from collections import Counter

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    # Constraints: 
    # n <= 10^5, nums[i] <= 5 * 10^4, queries.length <= 10^5
    # We need to find all gcd(nums[i], nums[j]) for i < j and sort them.
    # The number of pairs is n*(n-1)/2, which can be up to ~5 * 10^9.
    # However, the values in nums are small (up to 5 * 10^4).
    # Let's count occurrences of each value in nums.
    max_val = 0
    counts = Counter()
    for x in nums:
        counts[x] += 1
        if x > max_val:
            max_val = x
            
    # We can find the frequency of each possible GCD value.
    # A value g is a GCD of some pair (nums[i], nums[j]) if there are at least two numbers
    # in nums that are multiples of g, and their actual GCD is g.
    # Actually, it's easier to count how many pairs have a common divisor g.
    # Let f(g) be the number of elements in nums that are multiples of g.
    # The number of pairs (i, j) with i < j such that gcd(nums[i], nums[j]) is a multiple of g
    # is f(g) * (f(g) - 1) / 2.
    
    # Let count_gcd[g] be the number of pairs (i, j) with i < j such that gcd(nums[i], nums[j]) == g.
    # We can use inclusion-exclusion or a similar approach starting from max_val down to 1.
    count_gcd = [0] * (max_val + 1)
    
    # Precompute f(g) for all g
    f = [0] * (max_val + 1)
    for x, count in counts.items():
        # For each number x, find its divisors and add its count to f[divisor]
        # But it's more efficient to iterate over multiples of g.
        pass
    
    # Correct way to compute f(g):
    for g in range(1, max_val + 1):
        for multiple in range(g, max_val + 1, g):
            f[g] += counts[multiple]
            
    # Now count_gcd[g] = (number of pairs with gcd as a multiple of g) - sum(count_gcd[k] for k = 2g, 3g, ...)
    for g in range(max_val, 0, -1):
        num_pairs_with_multiple_g = f[g] * (f[g] - 1) // 2
        count_gcd[g] = num_pairs_with_multiple_g
        # Subtract pairs whose GCD is a strictly larger multiple of g
        for multiple in range(2 * g, max_val + 1, g):
            count_gcd[g] -= count_gcd[multiple]
            
    # Now we have the frequency of each GCD value.
    # We need to sort all gcdPairs and answer queries.
    # Since we know the frequencies, we can construct the sorted list conceptually.
    
    # The total number of pairs is n*(n-1)//2.
    # Let's build a prefix sum of counts to find the index in the sorted array.
    # Wait, the queries are indices into the SORTED gcdPairs.
    # So we need to iterate g from 1 to max_val and collect them in order.
    
    # The values of gcdPairs are sorted ascendingly.
    # We can find which value corresponds to each query by iterating through g = 1, 2, ...
    # but count_gcd[g] tells us how many times 'g' appears in the sorted list.
    
    # Let's build a mapping from index to value.
    # Since we need to answer queries efficiently, and there are up to 10^5 queries,
    # we can use the fact that count_gcd[g] is the frequency of g.
    
    # We want to find the value at query index.
    # The sorted list looks like: [1, 1, ..., 2, 2, ..., max_val, max_val]
    # where 'g' appears count_gcd[g] times.
    
    # Let's use a prefix sum of counts to find the range of indices for each g.
    # But we need them in sorted order of g.
    
    # Actually, since we want the value at query index, and queries are 0-indexed:
    # We can iterate g from 1 to max_val.
    # For each g, it occupies indices [current_idx, current_idx + count_gcd[g] - 1].
    
    # We can answer queries by sorting them or using a more direct approach.
    # Since we need to return an array of answers for the original order of queries:
    
    ans = [0] * len(queries)
    # To do this efficiently, let's sort the queries with their original indices.
    sorted_queries = sorted((q, i) for i, q in enumerate(queries))
    
    current_idx = 0
    query_ptr = 0
    for g in range(1, max_val + 1):
        if count_gcd[g] > 0:
            # All queries with indices in [current_idx, current_idx + count_gcd[g] - 1]
            # will have the answer 'g'.
            while query_ptr < len(sorted_queries) and sorted_queries[query_ptr][0] < current_idx + count_gcd[g]:
                ans[sorted_queries[query_ptr][1]] = g
                query_ptr += 1
            current_idx += count_gcd[g]
            
    return ans
