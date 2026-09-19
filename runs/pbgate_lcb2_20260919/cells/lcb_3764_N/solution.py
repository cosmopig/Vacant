from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    # For each row, we can take at most limits[i] elements.
    # To maximize the sum, we should pick the largest available elements from each row.
    # However, there's a global constraint of taking at most k elements in total.
    
    # First, sort each row in descending order to easily pick the largest elements.
    sorted_grid = []
    for i in range(len(grid)):
        row = sorted(grid[i], reverse=True)
        # We only care about at most limits[i] elements from this row.
        sorted_grid.append(row[:limits[i]])
    
    # Now we have a list of lists, where each inner list contains the best 
    # available elements for that row (up to its limit).
    # We need to pick at most k elements total from these lists to maximize sum.
    # Since all grid[i][j] >= 0, we should aim to pick as many as possible up to k.
    
    # This is a variation of the knapsack problem but simpler because each "item" 
    # (an element) has weight 1 and its value is its own value.
    # Actually, it's even simpler: we just want to pick the largest elements 
    # from all the available ones in sorted_grid.
    
    all_available_elements = []
    for row in sorted_grid:
        all_available_elements.extend(row)
    
    # Sort all collected candidates descending
    all_available_elements.sort(reverse=True)
    
    # Take the top k (or fewer if total available < k)
    return sum(all_available_elements[:k])

