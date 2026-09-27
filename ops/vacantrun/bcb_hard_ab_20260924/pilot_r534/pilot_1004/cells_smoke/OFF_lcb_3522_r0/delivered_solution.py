from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if consecutive and sorted in ascending order
        is_consecutive_sorted = True
        max_val = subarray[0]
        
        for j in range(k):
            if subarray[j] != subarray[0] + j:
                is_consecutive_sorted = False
                break
            if subarray[j] > max_val:
                max_val = subarray[j]
        
        if is_consecutive_sorted:
            results.append(max_val)
        else:
            results.append(-1)
            
    return results
