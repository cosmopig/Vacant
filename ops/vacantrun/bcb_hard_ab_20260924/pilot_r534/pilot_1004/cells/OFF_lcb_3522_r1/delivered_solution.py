from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []
    
    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        
        # Check if all elements are consecutive and sorted in ascending order.
        # This means for every j from 0 to k-2, subarray[j+1] == subarray[j] + 1.
        is_consecutive_sorted = True
        max_val = -1
        
        for j in range(k):
            if j > 0:
                if subarray[j] != subarray[j-1] + 1:
                    is_consecutive_sorted = False
                    break
            # Update max_val (though if consecutive sorted, it's just the last element)
            if subarray[j] > max_val:
                max_val = subarray[j]
        
        if is_consecutive_sorted:
            results.append(max_val)
        else:
            results.append(-1)
            
    return results
