from typing import List

def countPairs(nums: List[int]) -> int:
    def is_almost_equal(x: int, y: int) -> bool:
        s1 = str(x)
        s2 = str(y)
        L = max(len(s1), len(s2))
        s1 = s1.zfill(L)
        s2 = s2.zfill(L)
        
        if s1 == s2:
            return True
        
        diff_indices = []
        for i in range(L):
            if s1[i] != s2[i]:
                diff_indices.append(i)
                
        if len(diff_indices) != 2:
            return False
        
        i, j = diff_indices
        return s1[i] == s2[j] and s1[j] == s2[i]

    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if is_almost_equal(nums[i], nums[j]):
                count += 1
    return count
