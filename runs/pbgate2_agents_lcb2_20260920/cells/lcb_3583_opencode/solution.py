from typing import List

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    max_val = 0
    for x in nums:
        if x > max_val:
            max_val = x
    
    limit = max_val
    counts = [0] * (limit + 1)
    for x in nums:
        counts[x] += 1
        
    count_multiples = [0] * (limit + 1)
    for g in range(1, limit + 1):
        for multiple in range(g, limit + 1, g):
            count_multiples[g] += counts[multiple]
            
    exact_gcd = [0] * (limit + 1)
    for g in range(limit, 0, -1):
        pairs_with_multiple = (count_multiples[g] * (count_multiples[g] - 1)) // 2
        subtraction = 0
        for multiple in range(2 * g, limit + 1, g):
            subtraction += exact_gcd[multiple]
        exact_gcd[g] = pairs_with_multiple - subtraction
        
    sorted_gcds = []
    prefix_sums = []
    current_sum = 0
    for g in range(1, limit + 1):
        if exact_gcd[g] > 0:
            current_sum += exact_gcd[g]
            sorted_gcds.append(g)
            prefix_sums.append(current_sum)
            
    import bisect
    ans = []
    for q in queries:
        idx = bisect.bisect_left(prefix_sums, q + 1)
        # If q is exactly the last index of a value, bisect_left with q+1 will give that index.
        # Example: prefix_sums = [2, 3], queries = [0, 1, 2]
        # q=0: bisect_left([2, 3], 1) -> 0. sorted_gcds[0] = v1
        # q=1: bisect_left([2, 3], 2) -> 0. sorted_gcds[0] = v1
        # q=2: bisect_left([2, 3], 3) -> 1. sorted_gcds[1] = v2
        ans.append(sorted_gcds[idx])
        
    return ans
