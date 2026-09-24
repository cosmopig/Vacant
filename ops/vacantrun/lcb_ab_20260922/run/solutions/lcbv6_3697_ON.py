import math
from itertools import permutations

def minimumIncrements(nums, target):
    m = len(target)
    # Precompute LCMs for all non-empty subsets of indices
    lcm_map = {}
    for i in range(1, 1 << m):
        current_lcm = 1
        subset_indices = []
        for j in range(m):
            if (i >> j) & 1:
                current_lcm = math.lcm(current_lcm, target[j])
                subset_indices.append(j)
        lcm_map[i] = current_lcm

    # For each unique LCM, find the top m smallest costs and their indices
    unique_lcms = list(set(lcm_map.values()))
    best_costs = {}
    for l in unique_lcms:
        costs = []
        for j, val in enumerate(nums):
            cost = (l - (val % l)) % l
            costs.append((cost, j))
        costs.sort()
        # Keep only the top m smallest costs for each LCM
        best_costs[l] = costs[:m]

    def get_partitions(s):
        if not s:
            yield []
            return
        first = s[0]
        rest = s[1:]
        for partition in get_partitions(rest):
            # Option 1: first is in its own subset
            yield [[first]] + partition
            # Option 2: first is added to one of the existing subsets
            for i, subset in enumerate(partition):
                yield partition[:i] + [[first] + subset] + partition[i+1:]

    min_total_cost = float('inf')
    
    # Generate all partitions of indices {0, ..., m-1}
    indices = list(range(m))
    for partition in get_partitions(indices):
        # For each subset in the partition, find its LCM
        lcm_list = []
        for subset in partition:
            subset_mask = 0
            for idx in subset:
                subset_mask |= (1 << idx)
            lcm_list.append(lcm_map[subset_mask])
        
        # Solve the assignment problem for this partition
        # We have k subsets, each with an LCM from lcm_list
        # We want to pick distinct indices j_k to minimize sum of costs
        k = len(lcm_list)
        
        # Use backtracking to find the minimum cost for this partition
        def backtrack(subset_idx, used_indices, current_cost):
            nonlocal min_total_cost
            if subset_idx == k:
                min_total_cost = min(min_total_cost, current_cost)
                return
            
            l = lcm_list[subset_idx]
            for cost, idx in best_costs[l]:
                if idx not in used_indices:
                    used_indices.add(idx)
                    backtrack(subset_idx + 1, used_indices, current_cost + cost)
                    used_indices.remove(idx)

        backtrack(0, set(), 0)

    return min_total_cost

if __name__ == "__main__":
    # Example tests
    print(minimumIncrements([1,2,3], [4])) # Expected: 1
    print(minimumIncrements([8,4], [10,5])) # Expected: 2
    print(minimumIncrements([7,9,10], [7])) # Expected: 0
