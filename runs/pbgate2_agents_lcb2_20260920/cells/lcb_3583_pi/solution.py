from typing import List
import bisect

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    if not nums:
        return []
    
    max_num = max(nums)
    count = [0] * (max_num + 1)
    for x in nums:
        count[x] += 1
        
    # C[g] is the number of elements in nums that are multiples of g
    C = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        for multiple in range(g, max_num + 1, g):
            C[g] += count[multiple]
            
    # F[g] is the number of pairs (nums[i], nums[j]) such that gcd(nums[i], nums[j]) == g
    F = [0] * (max_num + 1)
    for g in range(max_num, 0, -1):
        total_pairs_multiple_g = C[g] * (C[g] - 1) // 2
        
        subtraction = 0
        for multiple in range(2 * g, max_num + 1, g):
            subtraction += F[multiple]
            
        F[g] = total_pairs_multiple_g - subtraction
        
    # Precompute prefix sums of counts to answer queries efficiently
    prefix_sums = [0] * (max_num + 2)
    for g in range(1, max_num + 1):
        prefix_sums[g+1] = prefix_sums[g] + F[g]
        
    ans = []
    for q in queries:
        # Find first g such that prefix_sums[g+1] > q
        idx = bisect.bisect_right(prefix_sums, q)
        ans.append(idx - 1)
        
    return ans
