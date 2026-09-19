from typing import List

def beautifulSplits(nums: List[int]) -> int:
    """
    Returns the number of ways to split an array into three subarrays nums1, nums2, and nums3
    such that nums = nums1 + nums2 + nums3 and (nums1 is a prefix of nums2 OR nums2 is a prefix of nums3).
    """
    n = len(nums)
    count = 0

    # A split into three non-empty subarrays requires at least 3 elements.
    # i is the end index of nums1 (exclusive), j is the end index of nums2 (exclusive).
    # nums1 = nums[0:i]
    # nums2 = nums[i:j]
    # nums3 = nums[j:n]
    # Constraints: 1 <= i < j < n
    for i in range(1, n - 1):
        nums1 = nums[:i]
        for j in range(i + 1, n):
            nums2 = nums[i:j]
            nums3 = nums[j:]

            # Check if nums1 is a prefix of nums2
            is_prefix1 = True
            min_len1 = min(len(nums1), len(nums2))
            for k in range(min_len1):
                if nums1[k] != nums2[k]:
                    is_prefix1 = False
                    break
            if is_prefix1 and len(nums1) <= len(nums2):
                count += 1
                continue # Avoid double counting if both conditions are met

            # Check if nums2 is a prefix of nums3
            is_prefix2 = True
            min_len2 = min(len(nums2), len(nums3))
            for k in range(min_len2):
                if nums2[k] != nums3[k]:
                    is_prefix2 = False
                    break
            if is_prefix2 and len(nums2) <= len(nums3):
                count += 1

    return count
