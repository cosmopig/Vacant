from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    candidates = []
    for i in range(len(grid)):
        # Sort row in descending order to get the largest elements first
        row_sorted = sorted(grid[i], reverse=True)
        # Only the top limits[i] elements from each row are potential candidates
        num_to_take = min(len(row_sorted), limits[i])
        candidates.extend(row_sorted[:num_to_take])
    
    # Sort all collected candidates in descending order
    candidates.sort(reverse=True)
    
    # The maximum sum of at most k elements is the sum of the top k candidates
    return sum(candidates[:k])
