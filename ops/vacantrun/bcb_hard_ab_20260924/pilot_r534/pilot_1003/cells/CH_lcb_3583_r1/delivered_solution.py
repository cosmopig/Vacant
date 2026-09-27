from typing import List
import bisect

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    if not nums:
        return []
    
    max_num = 0
    for x in nums:
        if x > max_num:
            max_num = x
            
    count = [0] * (max_num + 1)
    for x in nums:
        count[x] += 1
        
    f = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        for multiple in range(g, max_num + 1, g):
            f[g] += count[multiple]
            
    F = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        F[g] = f[g] * (f[g] - 1) // 2
        
    C = [0] * (max_num + 1)
    for g in range(max_num, 0, -1):
        C[g] = F[g]
        for multiple in range(2 * g, max_num + 1, g):
            C[g] -= C[multiple]
            
    p = [0] * (max_num + 1)
    for g in range(1, max_num + 1):
        p[g] = p[g-1] + C[g]
        
    results = []
    for q in queries:
        idx = bisect.bisect_right(p, q)
        # Since we want the smallest g such that p[g] > q, 
        # and p is non-decreasing, bisect_right gives us exactly that index.
        # However, if C[g] is 0 for some g, then p[g] = p[g-1].
        # If q falls into such a gap, we want the first g where p[g] > q.
        # Example: p = [0, 2, 2, 3], q=2. bisect_right returns index 3. Correct.
        results.append(idx)
    return results
