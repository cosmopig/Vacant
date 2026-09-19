from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)
    
    P = [0] * n
    curr_p = 0
    for i in range(n):
        curr_p += skill[i]
        P[i] = curr_p
        
    S = [0] * m
    # S_j = max_{i=0...n-1} (S_{j-1} + P_i * mana[j-1] - P_{i-1} * mana[j])
    # Let Q(j) = max_{i=0...n-1} (P_i * mana[j-1] - P_{i-1} * mana[j])
    # S_j = S_{j-1} + Q(j)
    # Since we want to minimize the total time, and all terms are positive, 
    # we can just compute S_j as the maximum possible value.
    
    for j in range(1, m):
        m_prev = mana[j-1]
        m_curr = mana[j]
        max_q = -float('inf')
        
        # Optimization: The expression is P_i * m_prev - P_{i-1} * m_curr
        # For i=0, it's P_0 * m_prev.
        # For i>0, it's P_i * m_prev - P_{i-1} * m_curr.
        
        # Let's try to optimize the loop. 25 million iterations in Python might be slow.
        # However, we can use a list comprehension or map for some speedup.
        
        # Actually, let's just write it clearly first and see if it passes.
        for i in range(n):
            p_prev = P[i-1] if i > 0 else 0
            val = P[i] * m_prev - p_prev * m_curr
            if val > max_q:
                max_q = val
        S[j] = S[j-1] + max_q
        
    return S[m-1] + P[n-1] * mana[m-1]
