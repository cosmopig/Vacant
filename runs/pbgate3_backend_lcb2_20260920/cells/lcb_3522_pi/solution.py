from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if all elements are consecutive and sorted in ascending order.
        # A subarray of size k is consecutive and sorted if:
        # 1. It's sorted (e.g., [1, 2, 3])
        # 2. The difference between adjacent elements is exactly 1.
        #    Wait, the problem says "consecutive and sorted in ascending order".
        #    Example 1: [1, 2, 3] -> max 3.
        #    Example 2: [2, 2, 2, 2, 2], k=4 -> [-1, -1]. This means [2, 2, 2, 2] is NOT consecutive/sorted?
        #    Actually, "consecutive" usually means x, x+1, x+2...
        #    Let's re-read: "Its maximum element if all of its elements are consecutive and sorted in ascending order."
        #    Example 3: [3,2,3,2,3,2], k=2. Subarrays: [3,2], [2,3], [3,2], [2,3], [3,2].
        #    Output: [-1, 3, -1, 3, -1].
        #    [2, 3] is consecutive and sorted -> max 3.
        #    [3, 2] is not sorted ascendingly.
        #    So [x, x+1, x+2, ..., x+k-1] is the required form.
        
        is_consecutive_sorted = True
        if k > 0:
            for j in range(k - 1):
                if subarray[j+1] != subarray[j] + 1:
                    is_consecutive_sorted = False
                    break
        else:
            # Should not happen based on constraints (1 <= k <= n)
            is_consecutive_sorted = True
            
        if is_consecutive_sorted:
            results.append(max(subarray))
        else:
            results.append(-1)
            
    return results
