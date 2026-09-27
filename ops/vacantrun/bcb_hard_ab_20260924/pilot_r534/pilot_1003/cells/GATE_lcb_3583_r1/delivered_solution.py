from typing import List
import bisect

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    if not nums:
        return []
    
    max_num = max(nums)
    freq = [0] * (max_num + 1)
    for x in nums:
        freq[x] += 1
        
    count = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        for multiple in range(g, max_num + 1, g):
            count[g] += freq[multiple]
            
    f = [0] * (max_num + 1)
    for g in range(max_num, 0, -1):
        F_g = (count[g] * (count[g] - 1)) // 2
        current_f = F_g
        for multiple in range(2 * g, max_num + 1, g):
            current_f -= f[multiple]
        f[g] = current_f
        
    prefix_sums = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        prefix_sums[g] = prefix_sums[g-1] + f[g]
        
    results = []
    for q in queries:
        idx = bisect.bisect_left(prefix_sums, q + 1)
        results.append(idx)
        
    return results
