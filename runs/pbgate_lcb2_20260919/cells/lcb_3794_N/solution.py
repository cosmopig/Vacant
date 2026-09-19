from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)
    
    W = [0] * (n + 1)
    for i in range(n):
        W[i+1] = W[i] + skill[i]
    
    S = [0] * m
    # S[0] is already 0.
    for j in range(1, m):
        max_val = -float('inf')
        m_prev = mana[j-1]
        m_curr = mana[j]
        for i in range(n):
            val = S[j-1] + W[i+1] * m_prev - W[i] * m_curr
            if val > max_val:
                max_val = val
        S[j] = max_val
        
    return S[m-1] + W[n] * mana[m-1]
