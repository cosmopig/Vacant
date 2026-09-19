from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)
    
    if not skill or not mana:
        return 0
        
    P = [0] * n
    current_sum = 0
    for i in range(n):
        current_sum += skill[i]
        P[i] = current_sum
        
    S = [0] * m
    # S[0] is always 0.
    for j in range(1, m):
        max_val = -float('inf')
        prev_mana = mana[j-1]
        curr_mana = mana[j]
        for i in range(n):
            p_i = P[i]
            p_prev = P[i-1] if i > 0 else 0
            val = S[j-1] + p_i * prev_mana - p_prev * curr_mana
            if val > max_val:
                max_val = val
        S[j] = max_val
        
    return int(S[m-1] + P[n-1] * mana[m-1])
