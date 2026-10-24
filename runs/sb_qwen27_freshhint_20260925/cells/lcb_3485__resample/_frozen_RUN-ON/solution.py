from typing import List

def maxPossibleScore(start: List[int], d: int) -> int:
    if len(start) < 2:
        return 0

    starts = sorted(start)
    low = 0
    high = starts[-1] + d - starts[0] + 1

    def feasible(x: int, starts=starts, d=d) -> bool:
        last = -10**30
        for s in starts:
            t = last + x
            if t < s:
                t = s
            if t > s + d:
                return False
            last = t
        return True

    while low < high:
        mid = (low + high + 1) // 2
        if feasible(mid):
            low = mid
        else:
            high = mid - 1

    return low
