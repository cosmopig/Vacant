from typing import List


def maxRemovals(source: str, pattern: str, targetIndices: List[int]) -> int:
    n = len(source)
    m = len(pattern)
    total_target = len(targetIndices)

    target = [0] * n
    for idx in targetIndices:
        target[idx] = 1

    # pos[c] stores 1-based pattern positions where pattern[j - 1] == c.
    pos = [[] for _ in range(26)]
    for j, ch in enumerate(pattern, 1):
        pos[ord(ch) - 97].append(j)

    # Iterate positions in descending order so one source character
    # cannot be used for multiple pattern characters.
    rev_pos = [lst[::-1] for lst in pos]

    INF = 10**9
    dp = [INF] * (m + 1)
    dp[0] = 0

    updates = [rev_pos[ord(ch) - 97] for ch in source]

    for i, upd in enumerate(updates):
        cost = target[i]
        for j in upd:
            val = dp[j - 1] + cost
            if val < dp[j]:
                dp[j] = val

    return total_target - dp[m]
