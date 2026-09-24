from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    res = [-1] * (n - k + 1)
    
    count = 1
    for i in range(n):
        if i > 0:
            if nums[i] == nums[i-1] + 1:
                count += 1
            else:
                count = 1
        
        if i >= k - 1:
            if count >= k:
                res[i - k + 1] = nums[i]
    return res
