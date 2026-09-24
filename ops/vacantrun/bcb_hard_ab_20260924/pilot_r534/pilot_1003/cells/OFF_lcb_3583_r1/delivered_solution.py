from typing import List
import math

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    if not nums or len(nums) < 2:
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
            
    # F[g] is the number of pairs (i, j) such that gcd(nums[i], nums[j]) == g
    F = [0] * (max_num + 1)
    for g in range(max_num, 0, -1):
        # Number of pairs whose GCD is a multiple of g
        total_pairs_multiple_g = C[g] * (C[g] - 1) // 2
        
        # Subtract pairs whose GCD is a strictly larger multiple of g
        subtraction = 0
        for multiple in range(2 * g, max_num + 1, g):
            subtraction += F[multiple]
        
        F[g] = total_pairs_multiple_g - subtraction
        
    # Prefix sums of F to find the value at each query index
    prefix_sum = [0] * (max_num + 1)
    current_sum = 0
    for g in range(1, max_num + 1):
        current_sum += F[g]
        prefix_sum[g] = current_sum
        
    ans = []
    for q in queries:
        # Binary search for the smallest g such that prefix_sum[g] > q
        low = 1
        high = max_num
        res = max_num
        while low <= high:
            mid = (low + high) // 2
            if prefix_sum[mid] > q:
                res = mid
                high = mid - 1
            else:
                low = mid + 1
        ans.append(res)
        
    return ans
