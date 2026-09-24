from typing import List
import bisect

def maximumCoins(coins: List[List[int]], k: int) -> int:
    if not coins:
        return 0
    
    # Sort segments by their starting position
    coins.sort()
    n = len(coins)
    ls = [c[0] for c in coins]
    rs = [c[1] for c in coins]
    cs = [c[2] for c in coins]
    
    # Precompute prefix sums of the total coins in each segment
    prefix_sum_full = [0] * (n + 1)
    for i in range(n):
        prefix_sum_full[i+1] = prefix_sum_full[i] + cs[i] * (rs[i] - ls[i] + 1)
        
    # The optimal window [x, x+k-1] will start at some l_i or end at some r_i.
    # Thus, the starting position x will be either l_i or r_i - k + 1.
    candidates = []
    for l, r, c in coins:
        candidates.append(l)
        candidates.append(r - k + 1)
    
    # Sort and remove duplicates from candidates to minimize checks
    candidates = sorted(list(set(candidates)))
    
    max_res = 0
    for x in candidates:
        # Find the range of segments that overlap with [x, x+k-1]
        # A segment i overlaps if rs[i] >= x and ls[i] <= x + k - 1.
        j = bisect.bisect_left(rs, x)
        m = bisect.bisect_right(ls, x + k - 1) - 1
        
        if j > m:
            continue
        
        # Calculate the sum of coins in the window [x, x+k-1]
        # For i in [j, m], the intersection is [max(ls[i], x), min(rs[i], x+k-1)]
        if j == m:
            current_sum = cs[j] * (min(rs[j], x + k - 1) - max(ls[j], x) + 1)
        else:
            # Segment j is the first one that ends >= x.
            # Segment m is the last one that starts <= x+k-1.
            # Segments in (j, m) are fully contained within [x, x+k-1].
            current_sum = cs[j] * (min(rs[j], x + k - 1) - max(ls[j], x) + 1)
            if j + 1 <= m - 1:
                current_sum += prefix_sum_full[m] - prefix_sum_full[j+1]
            # Add the contribution of segment m.
            current_sum += cs[m] * (min(rs[m], x + k - 1) - max(ls[m], x) + 1)
            
        if current_sum > max_res:
            max_res = current_sum
            
    return max_res
