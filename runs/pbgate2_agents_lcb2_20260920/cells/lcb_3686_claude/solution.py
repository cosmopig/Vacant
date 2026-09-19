from typing import List

def beautifulSplits(nums: List[int]) -> int:
    """
    Returns the number of ways to split an array into three subarrays nums1, nums2, and nums3
    such that nums = nums1 + nums2 + nums3 and (nums1 is a prefix of nums2 OR nums2 is a prefix of nums3).
    """
    n = len(nums)
    count = 0

    # A split into three non-empty subarrays requires at least 3 elements.
    # Let i be the end index of nums1 (exclusive), and j be the end index of nums2 (exclusive).
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
            is_prefix1 = False
            len1 = len(nums1)
            len2 = len(nums2)
            if len1 <= len2:
                if nums2[:len1] == nums1:
                    is_prefix1 = True

            # Check if nums2 is a prefix of nums3
            is_prefix2 = False
            len2 = len(nums2)
            len3 = len(nums3)
            if len2 <= len3:
                if nums3[:len2] == nums2:
                    is_prefix2 = True

            if is_prefix1 or is_prefix2:
                count += 1

    return count
