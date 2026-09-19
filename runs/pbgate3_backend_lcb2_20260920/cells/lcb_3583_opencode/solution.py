from typing import List
import math
from collections import Counter

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    max_num = 0
    for x in nums:
        if x > max_num:
            max_num = x
            
    count = [0] * (max_num + 1)
    for x in nums:
        count[x] += 1
        
    # count_multiples[g] is the number of elements in nums that are multiples of g
    count_multiples = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        for multiple in range(g, max_num + 1, g):
            count_multiples[g] += count[multiple]
            
    # gcd_counts[g] is the number of pairs (nums[i], nums[j]) such that gcd(nums[i], nums[j]) == g
    gcd_counts = [0] * (max_num + 1)
    for g in range(max_num, 0, -1):
        # Total pairs whose GCD is a multiple of g
        total_pairs_with_multiple_g = count_multiples[g] * (count_multiples[g] - 1) // 2
        
        # Subtract pairs where the GCD is a strictly larger multiple of g
        for multiple in range(2 * g, max_num + 1, g):
            total_pairs_with_multiple_g -= gcd_counts[multiple]
            
        gcd_counts[g] = total_pairs_with_multiple_g
        
    # Prepare the sorted list of GCDs
    # Since we need to access by index, and there are many duplicates, 
    # we can construct a prefix sum or just build the list.
    # However, n*(n-1)/2 can be up to 5*10^9, so we cannot build the full list.
    # We use the gcd_counts array to find values by index.
    
    # Precompute prefix sums of counts for sorted order (ascending)
    # The GCDs are in range [1, max_num]
    # But wait, the problem asks for the element at queries[i] in the SORTED list of all pairs.
    # We can use the gcd_counts to find which g corresponds to query index.
    
    # Let's build a prefix sum of counts from 1 to max_num
    # Actually, we need it sorted ascending.
    
    # Since queries[i] < n*(n-1)/2, and total pairs = sum(gcd_counts)
    # We can find the value by iterating through g from 1 to max_num.
    
    # Optimization: Precompute prefix sums of gcd_counts
    # But we need them in ascending order of g.
    
    # Let's re-evaluate: The sorted list is [g1, g2, ..., gk] where k = n(n-1)/2.
    # We want the value at index queries[i].
    # This is equivalent to finding the smallest g such that sum_{j=1}^{g} gcd_counts[j] > queries[i].
    
    # Wait, we need to be careful: if multiple pairs have same GCD, they are adjacent.
    # The sorted list contains all n(n-1)/2 values.
    # Example 1: nums=[2,3,4], gcdPairs=[1,2,1] -> sorted [1,1,2]. queries=[0,2,2] -> [1,2,2]
    # Here g=1 has count 2, g=2 has count 1.
    # Sorted list: index 0: 1, index 1: 1, index 2: 2.
    
    # So we need to find the smallest g such that prefix_sum[g] > queries[i].
    # Wait, if queries[i] is 0 and gcd_counts[1]=2, then it's 1.
    # If queries[i] is 1 and gcd_counts[1]=2, then it's 1.
    # If queries[i] is 2 and gcd_counts[1]=2, then it's the next g (which is 2).
    
    # Let's use a prefix sum array for gcd_counts.
    prefix_sums = [0] * (max_num + 1)
    current_sum = 0
    for g in range(1, max_num + 1):
        current_sum += gcd_counts[g]
        prefix_sums[g] = current_sum
        
    # To answer queries efficiently, we can use binary search on prefix_sums.
    import bisect
    
    ans = []
    for q in queries:
        # Find the first g such that prefix_sums[g] > q
        # bisect_right returns the leftmost insertion point to maintain order.
        # If we want the smallest g such that prefix_sums[g] >= q + 1,
        # it's exactly what bisect_right does on a list of prefix sums.
        idx = bisect.bisect_right(prefix_sums, q)
        ans.append(idx)
        
    return ans

# Wait, the logic for finding g is:
# The sorted list has gcd_counts[1] copies of 1, then gcd_counts[2] copies of 2, etc.
# Example 1: gcd_counts[1]=2, gcd_counts[2]=1. Sorted: [1, 1, 2]
# queries = [0, 2, 2]
# q=0: prefix_sums[1]=2. 2 > 0 is true at g=1. ans=1.
# q=2: prefix_sums[1]=2 (not > 2), prefix_sums[2]=3 (> 2). ans=2.
# Correct.

# One detail: the loop for gcd_counts must be correct.
# The current logic:
# total_pairs_with_multiple_g = count_multiples[g] * (count_multiples[g] - 1) // 2
# This is the number of pairs (i, j) such that gcd(nums[i], nums[j]) is a multiple of g.
# Let f(g) be the number of pairs with gcd exactly g.
# Then count_multiples[g] = sum_{k=1, 2, ...} f(k*g)
# So f(g) = (count_multiples[g] choose 2) - sum_{k=2, 3, ...} f(k*g)
# This is exactly what the loop does.

# Let's refine the solution to be more efficient and handle constraints.
# max_num = 50,000.
# count_multiples takes O(max_num * log(max_num))
# gcd_counts takes O(max_num * log(max_num))
# queries take O(Q * log(max_num))
# Total complexity is fine for 10^5 and 5*10^4.

import math
from typing import List
from collections import Counter
import bisect

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    max_num = 0
    for x in nums:
        if x > max_num:
            max_num = x
            
    count = [0] * (max_num + 1)
    for x in nums:
        count[x] += 1
        
    count_multiples = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        for multiple in range(g, max_num + 1, g):
            count_multiples[g] += count[multiple]
            
    gcd_counts = [0] * (max_num + 1)
    for g in range(max_num, 0, -1):
        total_pairs_with_multiple_g = count_multiples[g] * (count_multiples[g] - 1) // 2
        for multiple in range(2 * g, max_num + 1, g):
            total_pairs_with_multiple_g -= gcd_counts[multiple]
        gcd_counts[g] = total_pairs_with_multiple_g
        
    prefix_sums = [0] * (max_num + 1)
    current_sum = 0
    for g in range(1, max_num + 1):
        current_sum += gcd_counts[g]
        prefix_sums[g] = current_sum
        
    ans = []
    for q in queries:
        # We want the smallest g such that prefix_sums[g] > q
        # bisect_right(prefix_sums, q) returns index i such that all elements 
        # to the left are <= q and element at i is > q.
        idx = bisect.bisect_right(prefix_sums, q)
        ans.append(idx)
    return ans
