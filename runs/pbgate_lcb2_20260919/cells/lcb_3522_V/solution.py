from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if all elements are consecutive and sorted in ascending order.
        # This means:
        # 1. The subarray is sorted: subarray[j] < subarray[j+1] for all j.
        #    Wait, the example [2,2,2,2,2] with k=4 gives [-1,-1].
        #    If it were just "consecutive", maybe 2,2,2,2 is consecutive?
        #    But the definition says: "maximum element if all of its elements are consecutive and sorted in ascending order."
        #    Example 1: [1,2,3] -> max 3. [2,3,4] -> max 4.
        #    Example 2: [2,2,2,2,2], k=4 -> [-1,-1]. This implies they must be strictly increasing and consecutive.
        #    If it's "consecutive", usually it means x, x+1, x+2...
        #    Let's check Example 3: [3,2,3,2,3,2], k=2 -> [-1,3,-1,3,-1]
        #    Subarrays of size 2:
        #    [3,2] -> -1 (not sorted)
        #    [2,3] -> 3 (sorted and consecutive)
        #    [3,2] -> -1
        #    [2,3] -> 3
        #    [3,2] -> -1
        #    So [2,3] is valid.
        
        is_valid = True
        if k > 0:
            for j in range(k):
                # Check if sorted and consecutive
                # For a subarray to be consecutive and sorted in ascending order,
                # each element must be exactly 1 greater than the previous one.
                # Also, for k=1, it's always valid? Let's check.
                if j > 0:
                    if subarray[j] != subarray[j-1] + 1:
                        is_valid = False
                        break
        else:
            is_valid = False # Should not happen based on constraints

        if is_valid:
            results.append(max(subarray))
        else:
            results.append(-1)
            
    return results
