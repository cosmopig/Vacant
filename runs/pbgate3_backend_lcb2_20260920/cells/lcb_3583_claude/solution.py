from typing import List
import math
from collections import Counter

def gcdValues(nums: List[int], queries: List[int]) -> List[int]:
    # Constraints:
    # n <= 10^5, nums[i] <= 5 * 10^4, queries.length <= 10^5
    # We need to find all possible gcd(nums[i], nums[j]) for i < j.
    # The maximum value in nums is M = 50,000.

    max_val = 0
    for x in nums:
        if x > max_val:
            max_val = x

    # Count occurrences of each number in the input array
    counts = Counter(nums)

    # To find all possible GCDs, we can iterate through every possible divisor d from 1 to max_val.
    # For a fixed d, any pair (nums[i], nums[j]) such that both are multiples of d will have a GCD that is a multiple of d.
    # However, it's easier to count how many pairs have a common divisor d.
    # Let C(d) be the number of elements in `nums` that are divisible by d.
    # The number of pairs (i, j) with i < j such that both nums[i] and nums[j] are divisible by d is:
    # count_pairs(d) = C(d) * (C(d) - 1) / 2

    # We want to find the number of pairs whose GREATEST common divisor is exactly g.
    # Let F(g) be the number of pairs (i, j) such that gcd(nums[i], nums[j]) == g.
    # Then count_pairs(d) = sum_{k=1, k*d <= max_val} F(k*d).
    # By inclusion-exclusion (or Mobius inversion logic), we can find F(g) by iterating downwards from max_val to 1.

    count_divisible = [0] * (max_val + 1)
    for d in range(1, max_val + 1):
        for multiple in range(d, max_val + 1, d):
            count_divisible[d] += counts[multiple]

    f = [0] * (max_val + 1)
    # Iterate backwards to use the property: F(g) = count_pairs(g) - sum_{k=2, k*g <= max_val} F(k*g)
    for g in range(max_val, 0, -1):
        num_divisible = count_divisible[g]
        f[g] = (num_divisible * (num_divisible - 1)) // 2
        # Subtract counts of pairs whose GCD is a multiple of g (but strictly greater than g)
        for multiple in range(2 * g, max_val + 1, g):
            f[g] -= f[multiple]

    # Now we have the frequency of each GCD value.
    # We need to sort these values to answer queries.
    # The total number of pairs is n*(n-1)/2.
    # gcdPairs = sorted list of all gcd(nums[i], nums[j]).

    # Instead of building the full list (which could be 5*10^9 elements),
    # we use the frequencies to construct the sorted result conceptually.

    # Sort GCDs by value:
    sorted_gcds = []
    for g in range(1, max_val + 1):
        if f[g] > 0:
            sorted_gcds.append((g, f[g]))

    # sorted_gcds is already sorted by g because we iterated from 1 to max_val.
    # Wait, the problem says "sorting these values in ascending order".
    # My loop `for g in range(1, max_val + 1)` naturally processes them in ascending order.

    # To answer queries efficiently:
    # We can use a prefix sum of frequencies or just iterate through sorted_gcds.
    # Since we need to return the value at index queries[i], and there are many queries,
    # let's build a list of (value, count) pairs.

    # Actually, since we want the element at index `queries[i]`,
    # we can use the cumulative counts.

    results = []
    # Pre-calculate prefix sums or just iterate?
    # queries are up to 10^5, sorted_gcds is up to 5*10^4.
    # A simple linear scan for each query would be O(Q * M), too slow.
    # We need a faster way.

    # Let's build a list of (value, cumulative_count)
    # But we only need to know which value corresponds to the range [start, end].

    # Optimization:
    # The sorted gcdPairs looks like:
    # [1, 1, ..., 2, 2, ..., 3, 3, ...]
    # where each 'g' appears f[g] times.

    # We can use binary search or a simple pointer if queries were sorted.
    # Since they aren't necessarily sorted, let's just build the mapping.

    # Because we need to handle indices up to n*(n-1)/2 (which is 5*10^9),
    # we cannot expand the list. We must use the frequencies.

    # Let's create a sorted list of (value, count) and then answer queries.
    # Since g goes from 1 to max_val, sorted_gcds is already sorted by value.

    # To handle many queries efficiently:
    # We can use the fact that we only care about values where f[g] > 0.
    # Let's store (value, cumulative_count)

    cumulative = 0
    mapping = [] # list of (start_index, value)
    for g in range(1, max_val + 1):
        if f[g] > 0:
            mapping.append((cumulative, g))
            cumulative += f[g]

    # Now for each query q, we find the largest start_index <= q.
    # Since mapping is sorted by start_index, we can use binary search (bisect).
    import bisect

    ans = []
    for q in queries:
        # Find the entry where mapping[i][0] <= q < mapping[i+1][0]
        # We want the largest i such that mapping[i][0] <= q.
        idx = bisect.bisect_right(mapping, (q, float('inf'))) - 1
        if idx >= 0:
            ans.append(mapping[idx][1])
        else:
            # This shouldn't happen given constraints
            ans.append(0)

    return ans

```
