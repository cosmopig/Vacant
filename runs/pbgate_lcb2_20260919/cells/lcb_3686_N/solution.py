from typing import List

def beautifulSplits(nums: List[int]) -> int:
    n = len(nums)
    if n < 3:
        return 0
    
    # Precompute hashes for all prefixes to check prefix conditions in O(1)
    BASE = 53
    MOD = (1 << 61) - 1
    
    prefix_hash = [0] * (n + 1)
    pow_base = [1] * (n + 1)
    for i in range(n):
        prefix_hash[i+1] = (prefix_hash[i] * BASE + nums[i]) % MOD
        pow_base[i+1] = (pow_base[i] * BASE) % MOD
        
    def get_hash(l, r):
        return (prefix_hash[r] - prefix_hash[l] * pow_base[r-l]) % MOD

    count = 0
    # nums1 = nums[0:i], nums2 = nums[i:j], nums3 = nums[j:n]
    # Constraints: 1 <= i < j < n and each subarray must be non-empty.
    for i in range(1, n - 1):
        len1 = i
        # Precompute if nums1 is a prefix of some potential nums2 starting at i
        # This happens if get_hash(0, len1) == get_hash(i, i + len1) and j >= i + len1
        is_prefix1_possible = (i + len1 <= n - 1) and (get_hash(0, len1) == get_hash(i, i + len1))
        
        for j in range(i + 1, n):
            len2 = j - i
            len3 = n - j
            
            cond1 = False
            if is_prefix1_possible and len2 >= len1:
                cond1 = True
            
            cond2 = False
            if len3 >= len2:
                if get_hash(i, j) == get_hash(j, j + len2):
                    cond2 = True
            
            if cond1 or cond2:
                count += 1
                
    return count
