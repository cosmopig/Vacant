from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        is_consecutive_sorted = True
        for j in range(k - 1):
            if subarray[j+1] != subarray[j] + 1:
                is_consecutive_sorted = False
                break
        
        if is_consecutive_sorted:
            results.append(subarray[-1])
        else:
            results.append(-1)
    return results
