from typing import List

def maxSubarrays(n: int, conflictingPairs: List[List[int]]) -> int:
    # Sort pairs by R_k (the second element)
    pairs = []
    for a, b in conflictingPairs:
        l, r = min(a, b), max(a, b)
        pairs.append((l, r))
    
    # Sort by r
    pairs.sort(key=lambda x: x[1])
    
    v1 = [0] * (n + 1)
    v2 = [0] * (n + 1)
    c1 = [0] * (n + 1)
    
    best1, count1, best2 = 0, 0, 0
    pair_idx = 0
    num_pairs = len(pairs)
    
    for j in range(1, n + 1):
        while pair_idx < num_pairs and pairs[pair_idx][1] == j:
            l = pairs[pair_idx][0]
            if l > best1:
                best2 = best1
                best1 = l
                count1 = 1
            elif l == best1:
                count1 += 1
            elif l > best2:
                best2 = l
            pair_idx += 1
        v1[j] = best1
        v2[j] = best2
        c1[j] = count1
        
    total_bad = sum(v1)
    
    w = [0] * (n + 1)
    for j in range(1, n + 1):
        if c1[j] == 1:
            w[j] = v1[j] - v2[j]
            
    W = [0] * (n + 2)
    for j in range(1, n + 1):
        W[j+1] = W[j] + w[j]
        
    # To find the range where v1(j) == L_p
    start = {}
    end = {}
    for j in range(1, n + 1):
        if v1[j] != 0:
            if v1[j] not in start:
                start[v1[j]] = j
            end[v1[j]] = j
            
    max_reduction = 0
    for l, r in pairs:
        # Reduction for pair (l, r)
        # Range where v1(j) == l is [start[l], end[l]]
        if l in start:
            s = start[l]
            e = end[l]
            actual_start = max(r, s)
            if actual_start <= e:
                reduction = W[e+1] - W[actual_start]
                if reduction > max_reduction:
                    max_reduction = reduction
            
    return (n * (n + 1) // 2) - (total_bad - max_reduction)

