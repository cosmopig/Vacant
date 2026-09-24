from typing import List
import bisect

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    if not nums:
        return []
    
    max_val = 0
    for x in nums:
        if x > max_val:
            max_val = x
            
    freq = [0] * (max_val + 1)
    for x in nums:
        freq[x] += 1
        
    count = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        for multiple in range(g, max_val + 1, g):
            count[g] += freq[multiple]
            
    f = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        c_count = count[g]
        f[g] = c_count * (c_count - 1) // 2
        
    c = [0] * (max_val + 1)
    for g in range(max_val, 0, -1):
        c[g] = f[g]
        for multiple in range(2 * g, max_val + 1, g):
            c[g] -= c[multiple]
            
    prefix_sums = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        prefix_sums[g] = prefix_sums[g-1] + c[g]
        
    results = []
    for q in queries:
        # We want the smallest g such that prefix_sums[g] > q
        g = bisect.bisect_right(prefix_sums, q)
        results.append(g)
    return results
