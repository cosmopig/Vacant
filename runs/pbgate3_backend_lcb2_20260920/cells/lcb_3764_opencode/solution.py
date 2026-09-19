from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    # Sort each row in descending order to pick the largest elements first
    sorted_grid = []
    for i in range(len(grid)):
        row = sorted(grid[i], reverse=True)
        sorted_grid.append(row)
    
    # We want to select at most k elements total, with row limits.
    # This is a variation of the knapsack problem or a greedy approach 
    # if we consider that each element has weight 1 and value grid[i][j].
    # Since all weights are 1, we can use a greedy approach:
    # Collect all possible elements from each row up to its limit.
    candidates = []
    for i in range(len(grid)):
        limit = limits[i]
        # Take the top 'limit' elements from the sorted row
        for j in range(min(limit, len(sorted_grid[i]))):
            candidates.append(sorted_grid[i][j])
    
    # Sort all candidates globally and take the top k
    candidates.sort(reverse=True)
    return sum(candidates[:k])
