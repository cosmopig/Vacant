from typing import List

def beautifulSplits(nums: List[int]) -> int:
    n = len(nums)
    count = 0
    # A split into three subarrays nums1, nums2, nums3 means:
    # nums1 = nums[0:i]
    # nums2 = nums[i:j]
    # nums3 = nums[j:n]
    # where 1 <= i < j < n (each subarray must be non-empty)
    for i in range(1, n - 1):
        nums1 = nums[:i]
        for j in range(i + 1, n):
            nums2 = nums[i:j]
            nums3 = nums[j:]
            
            # Condition: nums1 is a prefix of nums2 OR nums2 is a prefix of nums3
            is_prefix1 = False
            if len(nums1) <= len(nums2):
                if nums2[:len(nums1)] == nums1:
                    is_prefix1 = True
            
            is_prefix2 = False
            if len(nums2) <= len(nums3):
                if nums3[:len(nums2)] == nums2:
                    is_prefix2 = True
            
            if is_prefix1 or is_prefix2:
                count += 1
    return count
