from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if all elements are consecutive and sorted in ascending order.
        # This means for a subarray of size k, the minimum must be min_val,
        # and it must contain every integer from min_val to min_val + k - 1.
        # Also, since they must be sorted, we can just check if each element
        # is exactly 1 greater than the previous one.
        
        is_consecutive_sorted = True
        for j in range(k):
            if j == 0:
                continue
            if subarray[j] != subarray[j-1] + 1:
                is_consecutive_sorted = False
                break
        
        if is_consecutive_sorted:
            results.append(subarray[-1])
        else:
            results.append(-1)
            
    return results
