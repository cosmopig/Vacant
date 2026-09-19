from typing import List
from collections import Counter

def subsequencesWithMiddleMode(nums: List[int]) -> int:
    MOD = 10**9 + 7
    n = len(nums)
    total_count = 0

    # Iterate over each possible middle index k.
    for k in range(2, n - 2):
        mid_val = nums[k]

        left_counts = Counter()
        for i in range(k):
            left_counts[nums[i]] += 1

        right_counts = Counter()
        for m in range(k + 1, n):
            right_counts[nums[m]] += 1

        count_mid_left = left_counts[mid_val]
        count_others_left = k - count_mid_left

        count_mid_right = right_counts[mid_val]
        count_others_right = (n - 1 - k) - count_mid_right

        # ways_l[x] is number of pairs from nums[:k] with exactly x mid_vals
        ways_l = [0, 0, 0]
        ways_l[2] = (count_mid_left * (count_mid_left - 1)) // 2
        ways_l[1] = count_mid_left * count_others_left
        ways_l[0] = (count_others_left * (count_others_left - 1)) // 2

        # ways_r[y] is number of pairs from nums[k+1:] with exactly y mid_vals
        ways_r = [0, 0, 0]
        ways_r[2] = (count_mid_right * (count_mid_right - 1)) // 2
        ways_r[1] = count_mid_right * count_others_right
        ways_r[0] = (count_others_right * (count_others_right - 1)) // 2

        for x in range(3):
            for y in range(3):
                F = 1 + x + y
                if ways_l[x] == 0 or ways_r[y] == 0:
                    continue

                current_ways = (ways_l[x] * ways_r[y]) % MOD

                if F >= 3:
                    total_count = (total_count + current_ways) % MOD
                elif F == 2:
                    # x+y=1. {nL, nR} is {1, 2}.
                    # We need to count pairs where the 3 non-mid elements are distinct.
                    nL = 2 - x
                    nR = 2 - y
                    bad = 0
                    if nL == 1 and nR == 2:
                        for v, c_l in left_counts.items():
                            if v == mid_val: continue
                            c_r = right_counts[v]
                            # Case {v} from left, {v, u} from right (u != v)
                            bad += c_l * c_r * (count_others_right - c_r)
                            # Case {v} from left, {v, v} from right
                            bad += c_l * (c_r * (c_r - 1) // 2)
                        total_count = (total_count + (current_ways - bad)) % MOD
                    elif nL == 2 and nR == 1:
                        for v, c_l in left_counts.items():
                            if v == mid_val: continue
                            c_r = right_counts[v]
                            # Case {v, v} from left, {v} from right
                            bad += (c_l * (c_l - 1) // 2) * c_r
                            # Case {v, u} from left, {v} from right (u != v)
                            bad += (c_l * (count_others_left - c_l)) * c_r
                        total_count = (total_count + (current_ways - bad)) % MOD
                elif F == 1:
                    pass # Always bad

    return total_count % MOD
