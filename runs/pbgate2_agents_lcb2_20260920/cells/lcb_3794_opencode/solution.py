from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)
    
    P = [0] * (n + 1)
    for i in range(n):
        P[i+1] = P[i] + skill[i]
        
    t_curr = 0
    for j in range(m - 1):
        mj = mana[j]
        mj1 = mana[j+1]
        # D_j = max_{i=0}^{n-1} (P_{i+1} * mana[j] - P_i * mana[j+1])
        max_d = max([P[i+1] * mj - P[i] * mj1 for i in range(n)])
        t_curr += max(0, max_d)
        
    return t_curr + P[n] * mana[m-1]
