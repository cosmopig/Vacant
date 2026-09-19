from typing import List

def minTime(skill: List[int], mana: List[int]) -> int:
    n = len(skill)
    m = len(mana)

    # P[i] is the sum of skills of wizards 0 to i-1.
    P = [0] * (n + 1)
    for i in range(n):
        P[i+1] = P[i] + skill[i]

    # T[j] is the start time of potion j at wizard 0.
    T = [0] * m

    # Iteratively calculate the earliest possible start time for each potion.
    for j in range(1, m):
        max_val = -float('inf')
        prev_mana = mana[j-1]
        curr_mana = mana[j]
        for i in range(n):
            # The constraint derived from "wizard i cannot work on two potions at once"
            val = T[j-1] + P[i+1] * prev_mana - P[i] * curr_mana
            if val > max_val:
                max_val = val
        T[j] = max_val

    # The total time is the completion time of the last potion by the last wizard.
    return T[m-1] + P[n] * mana[m-1]
