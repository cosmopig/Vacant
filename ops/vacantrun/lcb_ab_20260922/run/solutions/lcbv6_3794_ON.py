def minTime(skill, mana):
    n = len(skill)
    m = len(mana)
    
    P = [0] * n
    current_sum = 0
    for i in range(n):
        current_sum += skill[i]
        P[i] = current_sum
        
    S = [0] * m
    # S[0] is already 0
    
    # Pre-calculate P values to avoid repeated indexing if possible, 
    # but Python's list access is fast.
    
    for j in range(m - 1):
        mj = mana[j]
        mj1 = mana[j+1]
        
        max_val = P[0] * mj
        for i in range(1, n):
            val = P[i] * mj - P[i-1] * mj1
            if val > max_val:
                max_val = val
        S[j+1] = S[j] + max_val
        
    return S[m-1] + P[n-1] * mana[m-1]
