from typing import List

def beautifulSplits(nums: List[int]) -> int:
    n = len(nums)
    if n < 3:
        return 0
    
    P = 1000003
    MOD = (1 << 61) - 1
    
    h = [0] * (n + 1)
    p_pow = [1] * (n + 1)
    for i in range(n):
        h[i+1] = (h[i] * P + nums[i]) % MOD
        p_pow[i+1] = (p_pow[i] * P) % MOD
        
    def get_hash(l, r): # [l, r)
        return (h[r] - h[l] * p_pow[r-l]) % MOD

    count = 0
    cond1 = [False] * (n + 1)
    for i in range(1, n // 2 + 1):
        if get_hash(0, i) == get_hash(i, 2*i):
            cond1[i] = True

    for i in range(1, n):
        # Range for j is [i+1, n-1]
        # Condition 1: j >= 2*i and cond1[i]
        # Condition 2: j <= (n+i)//2 and get_hash(i, j) == get_hash(j, 2*j-i)
        
        if cond1[i]:
            start_j = max(i + 1, 2 * i)
            if start_j < n:
                count += (n - 1) - start_j + 1
            
            upper_j = min(n - 1, start_j - 1)
            for j in range(i + 1, upper_j + 1):
                if j <= (n+i)//2 and get_hash(i, j) == get_hash(j, 2*j-i):
                    count += 1
        else:
            upper_j = min(n - 1, (n + i) // 2)
            for j in range(i + 1, upper_j + 1):
                if get_hash(i, j) == get_hash(j, 2*j-i):
                    count += 1
    return count
