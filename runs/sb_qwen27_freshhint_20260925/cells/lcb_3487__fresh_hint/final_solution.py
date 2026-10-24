from typing import List


def maxRemovals(source: str, pattern: str, targetIndices: List[int]):
    n = len(source)
    m = len(pattern)
    total = len(targetIndices)

    is_target = [0] * n
    for idx in targetIndices:
        is_target[idx] = 1

    INF = 10**9
    dp = [INF] * (m + 1)
    dp[0] = 0

    positions = [[] for _ in range(26)]
    for j, ch in enumerate(pattern, 1):
        positions[ord(ch) - 97].append(j)

    for lst in positions:
        lst.reverse()

    updates = [positions[ord(ch) - 97] for ch in source]

    for i, js in enumerate(updates):
        if not js:
            continue

        if is_target[i]:
            for j in js:
                cand = dp[j - 1] + 1
                if cand < dp[j]:
                    dp[j] = cand
        else:
            for j in js:
                cand = dp[j - 1]
                if cand < dp[j]:
                    dp[j] = cand

        if dp[m] == 0:
            return total

    return total - dp[m]
