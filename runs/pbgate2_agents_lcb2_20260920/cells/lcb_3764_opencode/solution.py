from typing import List

def maxSum(grid: List[List[int]], limits: List[int], k: int) -> int:
    pool = []
    for i in range(len(grid)):
        row = sorted(grid[i], reverse=True)
        num_to_take = min(len(row), limits[i])
        pool.extend(row[:num_to_take])
    
    pool.sort(reverse=True)
    return sum(pool[:k])
