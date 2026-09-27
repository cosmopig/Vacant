from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    consecutive_count = 1
    
    for i in range(n):
        if i > 0:
            if nums[i] == nums[i-1] + 1:
                consecutive_count += 1
            else:
                consecutive_count = 1
        
        if i >= k - 1:
            if consecutive_count >= k:
                results.append(nums[i])
            else:
                results.append(-1)
    return results
