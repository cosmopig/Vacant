from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    # For each row, we can take at most limits[i] elements.
    # To maximize the sum, for each row i, we should sort its elements in descending order.
    # Then, from each row i, we can pick up to limits[i] largest elements.
    # However, we are limited by k total elements across all rows.
    
    # This is a variation of the knapsack problem or more specifically, 
    # picking items with weights (1) and values (the element value).
    # Since each row has its own limit, but we want to pick at most k overall,
    # we can treat all "available" elements as candidates.
    # An element in row i is a candidate if it's among the top limits[i] largest in that row.
    
    candidates = []
    for i in range(len(grid)):
        row = grid[i]
        row_sorted = sorted(row, reverse=True)
        # We can take at most limits[i] elements from this row.
        # Since we want to maximize the sum and all values are non-negative (0 <= grid[i][j]),
        # we should consider taking as many as possible up to limits[i], 
        # but only if they contribute to a total of k.
        # Actually, since we can take AT MOST k elements in total, and each element counts as 1,
        # we just need to collect all the best candidates from each row.
        for j in range(min(len(row_sorted), limits[i])):
            candidates.append(row_sorted[j])
    
    # Now we have a list of candidate elements, where each element is one of the 
    # top 'limits[i]' from its respective row.
    # We want to pick at most k elements from this candidates list to maximize sum.
    # Since all grid values are non-negative, we should pick the largest ones.
    candidates.sort(reverse=True)
    
    return sum(candidates[:k])

