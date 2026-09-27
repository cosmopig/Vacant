from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    res = [-1] * (n - k + 1)
    if k == 1:
        return nums
    
    consecutive = 1
    for i in range(1, n):
        if nums[i] == nums[i-1] + 1:
            consecutive += 1
        else:
            consecutive = 1
        
        if consecutive >= k:
            res[i - k + 1] = nums[i]
            
    return res
