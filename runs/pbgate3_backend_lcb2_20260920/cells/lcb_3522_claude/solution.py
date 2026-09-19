from typing import List

def resultsArray(nums: List[int], k: int) -> List[int]:
    n = len(nums)
    results = []

    for i in range(n - k + 1):
        subarray = nums[i : i + k]
        # Check if the subarray is consecutive and sorted in ascending order.
        # A subarray of size k is consecutive and sorted if:
        # 1. The difference between max and min is exactly k-1.
        # 2. All elements are unique (set length == k).
        # 3. The first element + (k-1) equals the last element (if sorted).
        # Actually, "consecutive and sorted in ascending order" means:
        # subarray[j] = subarray[0] + j for all j from 0 to k-1.

        is_valid = True
        max_val = -1
        for j in range(k):
            if subarray[j] != subarray[0] + j:
                is_valid = False
                break

        if is_valid:
            # The maximum element of a sorted consecutive array is the last one.
            results.append(subarray[-1])
        else:
            results.append(-1)

    return results
