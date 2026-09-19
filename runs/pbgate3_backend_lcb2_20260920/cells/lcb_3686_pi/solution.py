from typing import List

def beautifulSplits(nums: List[int]) -> int:
    n = len(nums)
    if n < 3:
        return 0
    
    count = 0
    # nums1 = nums[0:i]
    # nums2 = nums[i:j]
    # nums3 = nums[j:n]
    # Constraints: 1 <= i < j < n
    
    for i in range(1, n - 1):
        nums1 = nums[:i]
        len1 = len(nums1)
        
        is_p1_possible = False
        if i + len1 < n:
            if nums[i : i+len1] == nums1:
                is_p1_possible = True
        
        for j in range(i + 1, n):
            # Condition 1: nums1 is a prefix of nums2
            # nums2 = nums[i:j]. Length is j-i.
            # For nums1 to be a prefix of nums2, we need j-i >= len1 AND nums[i:i+len1] == nums1
            p1 = False
            if j - i >= len1 and is_p1_possible:
                p1 = True
            
            # Condition 2: nums2 is a prefix of nums3
            # nums2 = nums[i:j]. Length is j-i.
            # nums3 = nums[j:n]. Length is n-j.
            # For nums2 to be a prefix of nums3, we need n-j >= j-i AND nums[i:j] == nums[j:j+(j-i)]
            p2 = False
            len2 = j - i
            if n - j >= len2:
                # Check if nums[i:j] == nums[j:j+len2]
                match = True
                for k in range(len2):
                    if nums[i + k] != nums[j + k]:
                        match = False
                        break
                if match:
                    p2 = True
            
            if p1 or p2:
                count += 1
                
    return count
