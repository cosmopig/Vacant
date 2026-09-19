from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    # For each row, we can take at most limits[i] elements.
    # To maximize the sum, for each row i, we should consider taking 
    # up to limits[i] largest elements from that row.
    
    # However, there's a global constraint k on total elements taken.
    # This is a variation of the knapsack problem or more specifically,
    # selecting items with weights (count) and values (sum).
    # But here, each "item" is actually a set of elements from a row.
    # Actually, it's simpler: we want to pick at most k elements total.
    # Each element has a value grid[i][j]. 
    # The constraint is that for each row i, we can pick at most limits[i] elements.
    
    # Let's refine this:
    # For each row i, sort the elements in descending order.
    # Let sorted_row[i] be the sorted elements of grid[i].
    # We want to pick k elements total such that we don't exceed limits[i] for any i.
    # This is equivalent to: 
    # For each row i, only the first limits[i] largest elements are "available".
    # Once we have these available elements from all rows, we just need to pick 
    # the top k largest among all of them.
    
    all_available_elements = []
    for i in range(len(grid)):
        row = grid[i]
        row.sort(reverse=True)
        # Take at most limits[i] elements from this row
        num_to_take = min(len(row), limits[i])
        all_available_elements.extend(row[:num_to_take])
    
    # Sort all available elements in descending order and take the top k
    all_available_elements.sort(reverse=True)
    
    return sum(all_available_elements[:k])

