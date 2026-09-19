from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []

    for i in range(n - k + 1):
        subarray = nums[i : i + k]

        # Check if elements are consecutive and sorted in ascending order.
        # A subarray is consecutive and sorted if:
        # 1. It's sorted: all elements are non-decreasing (actually strictly increasing for distinct values).
        #    Wait, the problem says "consecutive and sorted". For integers, this means
        #    the difference between adjacent elements must be exactly 1.
        #    Example 1: [1,2,3] -> max is 3. Correct.
        #    Example 2: [2,2,2,2,2], k=4 -> [2,2,2,2]. Not consecutive (difference is 0). Output -1.
        #    Wait, "consecutive" usually means x, x+1, x+2...
        #    Let's re-read: "Its maximum element if all of its elements are consecutive and sorted in ascending order."
        #    Example 3: [3,2,3,2,3,2], k=2. Subarray [2,3] is consecutive and sorted. Max is 3.

        is_consecutive_sorted = True
        if k > 1:
            for j in range(k - 1):
                if subarray[j+1] != subarray[j] + 1:
                    is_consecutive_sorted = False
                    break
        else:
            # A single element is always consecutive and sorted.
            is_consecutive_sorted = True

        if is_consecutive_sorted:
            results.append(max(subarray))
        else:
            results.append(-1)

    return results
