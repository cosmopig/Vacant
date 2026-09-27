from typing import List

def countPairs(nums: List[int]):
    def is_almost_equal(x: int, y: int) -> bool:
        s1 = str(x)
        s2 = str(y)
        L = max(len(s1), len(s2))
        s1 = s1.zfill(L)
        s2 = s2.zfill(L)
        
        if s1 == s2:
            return True
        
        diffs = []
        for i in range(L):
            if s1[i] != s2[i]:
                diffs.append(i)
        
        if len(diffs) == 2:
            idx1, idx2 = diffs
            return s1[idx1] == s2[idx2] and s1[idx2] == s2[idx1]
        
        return False

    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if is_almost_equal(nums[i], nums[j]):
                count += 1
    return count
