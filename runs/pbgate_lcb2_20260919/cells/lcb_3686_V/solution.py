from typing import List

def beautifulSplits(nums: List[int]) -> int:
    n = len(nums)
    if n < 3:
        return 0
    count = 0
    # nums1 = nums[0:i], nums2 = nums[i:j], nums3 = nums[j:n]
    # Constraints: 1 <= i, j-i >= 1, n-j >= 1  => 1 <= i < j < n
    for i in range(1, n - 1):
        nums1 = nums[:i]
        len1 = len(nums1)
        # Precompute if nums1 is a prefix of any possible nums2 starting at i
        # This means for some j > i, nums[i:j] starts with nums1.
        # Since we need to check this inside the loop over j, let's optimize.
        
        for j in range(i + 1, n):
            nums2 = nums[i:j]
            len2 = len(nums2)
            nums3 = nums[j:]
            len3 = len(nums3)
            
            is_prefix1 = False
            if len1 <= len2:
                # Check if nums1 is prefix of nums2
                # nums1 is nums[0:i], nums2 is nums[i:j]
                # This means nums[k] == nums[i+k] for k in 0..len1-1
                is_prefix1 = True
                for k in range(len1):
                    if nums[k] != nums[i + k]:
                        is_prefix1 = False
                        break
            
            is_prefix2 = False
            if len2 <= len3:
                # Check if nums2 is prefix of nums3
                # nums2 is nums[i:j], nums3 is nums[j:n]
                # This means nums[i+k] == nums[j+k] for k in 0..len2-1
                is_prefix2 = True
                for k in range(len2):
                    if nums[i + k] != nums[j + k]:
                        is_prefix2 = False
                        break
            
            if is_prefix1 or is_prefix2:
                count += 1
    return count
