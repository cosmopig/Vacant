from typing import List


def maxRemovals(source: str, pattern: str, targetIndices: List[int]) -> int:
    n = len(source)
    m = len(pattern)

    removable = [False] * n
    for idx in targetIndices:
        removable[idx] = True

    # For each character, store 1-based pattern positions where it appears,
    # in descending order so each source character is used at most once.
    positions = {}
    for j in range(m, 0, -1):
        ch = pattern[j - 1]
        if ch in positions:
            positions[ch].append(j)
        else:
            positions[ch] = [j]

    INF = 10 ** 9
    dp = [INF] * (m + 1)
    dp[0] = 0

    empty = []
    get_positions = positions.get

    for i, ch in enumerate(source):
        cost = removable[i]
        for j in get_positions(ch, empty):
            val = dp[j - 1] + cost
            if val < dp[j]:
                dp[j] = val

    return len(targetIndices) - dp[m]
