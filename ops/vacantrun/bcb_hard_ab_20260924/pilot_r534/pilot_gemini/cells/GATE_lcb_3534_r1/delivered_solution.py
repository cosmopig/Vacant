from typing import List

def countPairs(nums: List[int]) -> int:
    def are_almost_equal(x: int, y: int) -> bool:
        s1 = str(x)
        s2 = str(y)
        L = max(len(s1), len(s2))
        s1 = s1.zfill(L)
        s2 = s2.zfill(L)
        
        diff_indices = []
        for i in range(L):
            if s1[i] != s2[i]:
                diff_indices.append(i)
        
        if len(diff_indices) == 0:
            return True
        if len(diff_indices) == 2:
            i, j = diff_indices
            return s1[i] == s2[j] and s1[j] == s2[i]
        return False

    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if are_almost_equal(nums[i], nums[j]):
                count += 1
    return count
