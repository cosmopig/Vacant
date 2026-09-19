from typing import List
import math
from collections import Counter

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    # Constraints:
    # n <= 10^5, nums[i] <= 5 * 10^4, queries.length <= 10^5
    # We need to find all possible gcd(nums[i], nums[j]) for i < j.
    # The number of pairs is up to n*(n-1)/2, which is ~5*10^9 (too many to iterate).
    # However, the values in nums are small: max_val = 5 * 10^4.

    max_val = 0
    for x in nums:
        if x > max_val:
            max_val = x

    # Count occurrences of each number in nums
    counts = Counter(nums)

    # We want to find how many pairs (i, j) have gcd(nums[i], nums[j]) == g.
    # Let f(g) be the number of pairs (i, j) such that g divides both nums[i] and nums[j].
    # If we know f(g), we can find h(g), the number of pairs with gcd exactly equal to g.
    # h(g) = sum_{k=1, 2, ... where k*g <= max_val} mu(k) * f(k*g)
    # Or more simply using inclusion-exclusion:
    # f(g) is the number of pairs from elements that are multiples of g.
    # Let count_multiples(g) be the number of elements in nums divisible by g.
    # Then f(g) = count_multiples(g) * (count_multiples(g) - 1) // 2.

    count_multiples = [0] * (max_val + 1)
    for x, count in counts.items():
        # For each number, find all its divisors and increment their counts?
        # No, it's better to iterate over multiples of g.
        pass

    # Correct approach:
    # 1. Count occurrences of each value in nums.
    # 2. Calculate count_multiples[g] for every g from 1 to max_val.
    for x, count in counts.items():
        # This is still slow if we do it for every x.
        # Instead, iterate over all possible values v that exist in nums.
        pass

    # Let's refine:
    count_multiples = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        for multiple in range(g, max_val + 1, g):
            count_multiples[g] += counts[multiple]

    # f(g) = number of pairs (i, j) such that gcd(nums[i], nums[j]) is a multiple of g.
    f = [0] * (max_val + 1)
    for g in range(1, max_val + 1):
        c = count_multiples[g]
        f[g] = c * (c - 1) // 2

    # h(g) = number of pairs (i, j) such that gcd(nums[i], nums[j]) is exactly g.
    # We can use the property: f(g) = sum_{k=1}^{max_val/g} h(k*g)
    # So we can compute h(g) from max_val down to 1.
    h = [0] * (max_val + 1)
    for g in range(max_val, 0, -1):
        h[g] = f[g]
        for multiple in range(2 * g, max_val + 1, g):
            h[g] -= h[multiple]

    # Now we have the counts of each GCD value.
    # We need to sort these values and answer queries.
    # The problem asks for gcdPairs sorted in ascending order.
    # This means if a GCD 'v' appears h[v] times, it occupies indices
    # from (sum of h[k] for k < v) to (sum of h[k] for k <= v).

    gcd_sorted = []
    for g in range(1, max_val + 1):
        if h[g] > 0:
            gcd_sorted.extend([g] * h[g])

    # The queries are 0-indexed.
    return [gcd_sorted[q] for q in queries]

```
