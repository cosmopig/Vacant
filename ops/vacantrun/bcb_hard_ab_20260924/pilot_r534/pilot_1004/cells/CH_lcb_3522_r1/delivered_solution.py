from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if all elements are consecutive and sorted in ascending order.
        # A subarray of size k is consecutive and sorted if:
        # 1. It's sorted: subarray[j] < subarray[j+1] for all j (Wait, "consecutive" usually means difference is 1)
        # Let's re-read the definition: "Its maximum element if all of its elements are consecutive and sorted in ascending order."
        # Example 1: [1,2,3] -> max 3. [2,3,4] -> max 4. [3,4,3] -> -1 (not sorted). [4,3,2] -> -1 (not sorted/ascending). [3,2,5] -> -1 (not consecutive).
        # Example 2: [2,2,2,2,2], k=4. Subarray [2,2,2,2]. Not consecutive? Or not strictly increasing?
        # "consecutive and sorted in ascending order" usually means x, x+1, x+2...
        # Let's check Example 2: nums = [2,2,2,2,2], k=4. Output is [-1,-1].
        # This implies that [2,2,2,2] is NOT considered "consecutive and sorted in ascending order".
        # If it were just "sorted", it would be 2. But it's -1.
        # So they must be strictly increasing by 1.
        
        is_valid = True
        if k == 0: # Should not happen based on constraints
            is_valid = False
        else:
            for j in range(k):
                # Check if it's the sequence starting from subarray[0] with step 1
                if subarray[j] != subarray[0] + j:
                    is_valid = False
                    break
        
        if is_valid:
            results.append(max(subarray))
        else:
            results.append(-1)
            
    return results
