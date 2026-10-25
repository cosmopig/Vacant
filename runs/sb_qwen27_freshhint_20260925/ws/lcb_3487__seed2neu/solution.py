from typing import List

def maxRemovals(source: str, pattern: str, targetIndices: List[int]) -> int:
    n = len(source)
    m = len(pattern)
    t_count = len(targetIndices)

    is_target = [False] * n
    for idx in targetIndices:
        is_target[idx] = True

    matches = [[] for _ in range(26)]
    for j, ch in enumerate(pattern, 1):
        matches[ord(ch) - 97].append(j)

    for lst in matches:
        lst.reverse()

    INF = t_count + 1
    dp = [INF] * (m + 1)
    dp[0] = 0

    for i, ch in enumerate(source):
        lst = matches[ord(ch) - 97]
        if not lst:
            continue

        if is_target[i]:
            for j in lst:
                val = dp[j - 1] + 1
                if val < dp[j]:
                    dp[j] = val
        else:
            for j in lst:
                val = dp[j - 1]
                if val < dp[j]:
                    dp[j] = val

    return t_count - dp[m]
