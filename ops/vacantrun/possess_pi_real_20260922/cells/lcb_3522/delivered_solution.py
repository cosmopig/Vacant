from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    for i in range(n - k + 1):
        is_consecutive_sorted = True
        if k > 1:
            for j in range(i, i + k - 1):
                if nums[j+1] - nums[j] != 1:
                    is_consecutive_sorted = False
                    break
        
        if is_consecutive_sorted:
            results.append(nums[i + k - 1])
        else:
            results.append(-1)
    return results
