from typing import List
from math import isqrt

def minNumberOfSeconds(mountainHeight: int, workerTimes: List[int]) -> int:
    h = mountainHeight
    times = workerTimes

    lo = 0
    hi = min(times) * h * (h + 1) // 2
    sqrt = isqrt

    while lo < hi:
        mid = (lo + hi) // 2
        total = 0

        for t in times:
            cap = mid // t
            total += (sqrt(1 + 8 * cap) - 1) // 2
            if total >= h:
                break

        if total >= h:
            hi = mid
        else:
            lo = mid + 1

    return lo
