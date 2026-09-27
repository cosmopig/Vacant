def assignElements(groups, elements):
    max_val = 100000
    # first_occurrence[v] stores the smallest index j such that elements[j] == v
    first_occurrence = {}
    for i, val in enumerate(elements):
        if val not in first_occurrence:
            first_occurrence[val] = i
            
    # ans_idx[x] will store the smallest index j such that x % elements[j] == 0
    ans_idx = [float('inf')] * (max_val + 1)
    
    for v, idx in first_occurrence.items():
        if v > max_val:
            continue
        # For each element value v, it can be assigned to any group size m which is a multiple of v
        # We want the smallest index j, so we update ans_idx[m] if current idx is smaller
        for m in range(v, max_val + 1, v):
            if idx < ans_idx[m]:
                ans_idx[m] = idx
                
    result = []
    for g in groups:
        res = float('inf')
        if g <= max_val:
            res = ans_idx[g]
        
        if res == float('inf'):
            result.append(-1)
        else:
            result.append(int(res))
            
    return result
