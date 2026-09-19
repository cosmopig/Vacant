from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)

    P = [0] * n
    curr_sum = 0
    for i in range(n):
        curr_sum += skill[i]
        P[i] = curr_sum

    # S[j] is the start time of potion j at wizard 0.
    S = [0] * m

    # We want to find the minimum S[m-1].
    # S[j+1] = max_{i=0...n-1} (S[j] + P[i]*mana[j] - P[i-1]*mana[j+1])
    # where P[-1] = 0.

    for j in range(m - 1):
        mj = mana[j]
        mj_next = mana[j+1]
        sj = S[j]
        max_s_next = 0
        for i in range(n):
            prev_p = P[i-1] if i > 0 else 0
            val = sj + P[i] * mj - prev_p * mj_next
            if val > max_s_next:
                max_s_next = val
        S[j+1] = max_s_next

    return S[m-1] + P[n-1] * mana[m-1]
