from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if all elements are consecutive and sorted in ascending order.
        # This means:
        # 1. The subarray is sorted: subarray[j] < subarray[j+1] for all j
        #    Wait, the problem says "consecutive and sorted". 
        #    Example 2: [2,2,2,2,2], k=4 -> Output [-1,-1]. 
        #    This means they must be strictly increasing by 1.
        #    Actually, let's re-read: "consecutive and sorted in ascending order".
        #    Example 1: [1,2,3] is consecutive and sorted. Max is 3.
        #    [2,3,4] is consecutive and sorted. Max is 4.
        #    [3,4,3] not consecutive.
        #    [4,3,2] not sorted (it's descending).
        #    [3,2,5] not consecutive.
        
        is_valid = True
        for j in range(k - 1):
            if subarray[j+1] != subarray[j] + 1:
                is_valid = False
                break
        
        if is_valid:
            results.append(max(subarray))
        else:
            results.append(-1)
            
    return results
