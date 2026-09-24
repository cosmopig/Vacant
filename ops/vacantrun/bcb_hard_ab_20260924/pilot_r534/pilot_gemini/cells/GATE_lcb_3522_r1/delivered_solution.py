from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    if n == 0:
        return []
    
    count = [1] * n
    for i in range(1, n):
        if nums[i] == nums[i-1] + 1:
            count[i] = count[i-1] + 1
        else:
            count[i] = 1
            
    results = []
    for i in range(k - 1, n):
        if count[i] >= k:
            results.append(nums[i])
        else:
            results.append(-1)
            
    return results
