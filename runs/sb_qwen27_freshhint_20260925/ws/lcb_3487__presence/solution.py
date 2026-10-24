from typing import List


def maxRemovals(source: str, pattern: str, targetIndices: List[int]) -> int:
    n = len(source)
    m = len(pattern)

    is_target = [False] * n
    for idx in targetIndices:
        is_target[idx] = True

    INF = 10**9
    dp = [INF] * (m + 1)
    dp[0] = 0

    positions = [[] for _ in range(26)]
    base = ord("a")
    for j, ch in enumerate(pattern, 1):
        positions[ord(ch) - base].append(j)

    for i, ch in enumerate(source):
        js = positions[ord(ch) - base]
        if not js:
            continue

        cost = 1 if is_target[i] else 0
        for j in reversed(js):
            candidate = dp[j - 1] + cost
            if candidate < dp[j]:
                dp[j] = candidate

    if dp[m] == INF:
        return 0

    return len(targetIndices) - dp[m]
