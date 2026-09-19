from typing import List
import math
from collections import Counter

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    # Constraints: 
    # n <= 10^5, nums[i] <= 5 * 10^4, queries.length <= 10^5
    # We need to find all gcd(nums[i], nums[j]) for i < j and sort them.
    # The number of pairs is n*(n-1)/2, which can be up to ~5 * 10^9.
    # However, the values in nums are small (up to 5 * 10^4).
    
    max_val = 0
    counts = Counter()
    for x in nums:
        counts[x] += 1
        if x > max_val:
            max_val = x
            
    # f[g] is the count of numbers divisible by g.
    f = [0] * (max_val + 1)
    for x, count in counts.items():
        # This part can be slow if we iterate over all divisors for each unique x.
        # But since max_val is small (5*10^4), it's better to iterate over multiples of g.
        pass

    # Let's use the property that count_divisible[g] = sum(f[j] for j in range(g, max_val + 1, g))
    # where f[j] is the frequency of value j in nums.
    freq = [0] * (max_val + 1)
    for x in nums:
        freq[x] += 1
        
    count_divisible = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        for multiple in range(g, max_val + 1, g):
            count_divisible[g] += freq[multiple]
            
    # h[g] is the number of pairs (i, j) with i < j such that gcd(nums[i], nums[j]) == g.
    h = [0] * (max_val + 1)
    for g in range(max_val, 0, -1):
        total_pairs_divisible_by_g = count_divisible[g] * (count_divisible[g] - 1) // 2
        h[g] = total_pairs_divisible_by_g
        for multiple in range(2 * g, max_val + 1, g):
            h[g] -= h[multiple]
            
    # The sorted gcdPairs are:
    # [1]*h[1], [2]*h[2], ..., [max_val]*h[max_val]
    # Since we want the value at index queries[i], and 1 < 2 < ... < max_val,
    # this is already sorted.
    
    prefix_sums = [0] * (max_val + 2)
    for g in range(1, max_val + 1):
        prefix_sums[g+1] = prefix_sums[g] + h[g]
        
    ans = []
    for q in queries:
        # Binary search for the smallest g such that prefix_sums[g+1] > q.
        low = 1
        high = max_val
        res = max_val
        while low <= high:
            mid = (low + high) // 2
            if prefix_sums[mid+1] > q:
                res = mid
                high = mid - 1
            else:
                low = mid + 1
        ans.append(res)
        
    return ans
