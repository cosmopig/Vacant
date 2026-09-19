from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)
    if n == 0 or m == 0:
        return 0
    
    prefix_skill = [0] * n
    curr_sum = 0
    for i in range(n):
        curr_sum += skill[i]
        prefix_skill[i] = curr_sum
        
    s_j = 0
    # S[0] is always 0. We need to compute S[1], S[2], ..., S[m-1].
    # Each S[j] = S[j-1] + max(P(0, j-1), max_{i=1..n-1} (P(i, j-1) - P(i-1, j)))
    # where P(i, k) = prefix_skill[i] * mana[k].
    
    current_s = 0
    for j in range(1, m):
        m_prev = mana[j-1]
        m_curr = mana[j]
        
        max_val = prefix_skill[0] * m_prev
        for i in range(1, n):
            val = prefix_skill[i] * m_prev - prefix_skill[i-1] * m_curr
            if val > max_val:
                max_val = val
        current_s += max_val
    
    # The final answer is S(m-1, 0) + P(n-1, m-1)
    # S(m-1, 0) is current_s.
    # P(n-1, m-1) = prefix_skill[n-1] * mana[m-1].
    return current_s + prefix_skill[n-1] * mana[m-1]
