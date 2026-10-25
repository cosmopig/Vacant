from typing import List


def maxRemovals(source: str, pattern: str, targetIndices: List[int]) -> int:
    m = len(pattern)

    marked = [False] * len(source)
    for idx in targetIndices:
        marked[idx] = True

    # by_char[c] contains pattern positions (1-based) whose character is c,
    # in descending order so in-place DP does not reuse the same source char.
    by_char = [[] for _ in range(26)]
    for j in range(m, 0, -1):
        by_char[ord(pattern[j - 1]) - 97].append(j)

    INF = 10 ** 9
    dp = [INF] * (m + 1)
    dp[0] = 0

    src_codes = [ord(ch) - 97 for ch in source]

    for i, code in enumerate(src_codes):
        cost = 1 if marked[i] else 0
        for j in by_char[code]:
            val = dp[j - 1] + cost
            if val < dp[j]:
                dp[j] = val

    return len(targetIndices) - dp[m]
