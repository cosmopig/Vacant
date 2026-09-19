from typing import List

def subsequencesWithMiddleMode(nums: List[int]) -> int:
    MOD = 10**9 + 7
    n = len(nums)
    if n < 5:
        return 0

    count_l = {}
    count_r = {}
    for x in nums:
        count_r[x] = count_r.get(x, 0) + 1

    total_L = 0
    sum_sq_L = 0
    total_R = sum(count_r.values())
    sum_sq_R = sum(v*v for v in count_r.values())

    ans = 0
    unique_vals = list(set(nums))

    for i in range(n):
        c = nums[i]

        # Step 1: Move nums[i] from count_r to "middle"
        rc = count_r[c]
        count_r[c] -= 1
        total_R -= 1
        sum_sq_R -= (rc*rc)
        sum_sq_R += ((rc-1)*(rc-1))

        # Now count_l is nums[:i] and count_r is nums[i+1:]
        lc = count_l.get(c, 0)
        rc = count_r.get(c, 0)
        tl = total_R - rc # Wait, total_R already has c removed? No, total_R was sum of all counts in count_r.
        # Let's re-verify:
        # Initially count_r is nums[0:].
        # At i=0:
        #   c = nums[0]
        #   count_r[c] becomes count_r[c]-1 (so it represents counts in nums[1:])
        #   total_R becomes sum(counts in nums[1:])
        #   sum_sq_R becomes sum(counts^2 in nums[1:])
        # This is correct.

        tl = total_R - rc # Wait, count_r already has c decremented.
        # So the number of non-c elements in count_r is (total_R - rc).
        # Let's use clearer names.

        # Current counts:
        # count_l: nums[:i]
        # count_r: nums[i+1:]
        # c = nums[i]

        cur_lc = count_l.get(c, 0)
        cur_rc = count_r.get(c, 0)

        # Number of non-c elements in left and right
        num_L_other = total_L - cur_lc
        num_R_other = total_R - cur_rc

        # Sum of squares of counts of non-c elements in left and right
        sum_sq_L_other = sum_sq_L - cur_lc**2
        sum_sq_R_other = sum_sq_R - cur_rc**2

        # Case f_c = 5: pick 2 from left, 2 from right (all are c)
        ways5 = (cur_lc * (cur_lc - 1) // 2) * (cur_rc * (cur_rc - 1) // 2)
        ans = (ans + ways5) % MOD

        # Case f_c = 4: pick 3 more c's and 1 non-c
        ways4a = (cur_lc * (cur_lc - 1) // 2) * cur_rc * num_R_other
        ways4b = cur_lc * num_L_other * (cur_rc * (cur_rc - 1) // 2)
        ans = (ans + ways4a + ways4b) % MOD

        # Case f_c = 3: pick 2 more c's and 2 non-c's
        ways3a = (cur_lc * (cur_lc - 1) // 2) * (num_R_other * (num_R_other - 1) // 2)
        ways3b = cur_lc * cur_rc * num_L_other * num_R_other
        ways3c = (num_L_other * (num_L_other - 1) // 2) * (cur_rc * (cur_rc - 1) // 2)
        ans = (ans + ways3a + ways3b + ways3c) % MOD

        # Case f_c = 2: pick 1 more c and 3 distinct non-c's
        waysA = 0
        for v in unique_vals:
            if v == c: continue
            cvl = count_l.get(v, 0)
            cvr = count_r.get(v, 0)
            # One from L (non-c), two distinct from R (non-c)
            if num_R_other > cvr:
                ways_to_pick_2 = ((num_R_other - cvr)**2 - (sum_sq_R_other - cvr**2)) // 2
                waysA = (waysA + cvl * ways_to_pick_2) % MOD

        waysB = 0
        for v in unique_vals:
            if v == c: continue
            cvl = count_l.get(v, 0)
            cvr = count_r.get(v, 0)
            # Two distinct from L (non-c), one from R (non-c)
            if num_L_other > cvl:
                ways_to_pick_2 = ((num_L_other - cvl)**2 - (sum_sq_L_other - cvl**2)) // 2
                waysB = (waysB + cvr * ways_to_pick_2) % MOD

        ans = (ans + waysA + waysB) % MOD

        # Step 2: Move nums[i] from "middle" to count_l
        count_l[c] = count_l.get(c, 0) + 1
        total_L += 1
        sum_sq_L -= (cur_lc**2) # Wait, cur_lc was the value BEFORE incrementing? No, it's the current one.
        # Let's be very careful here.
        # At this point in the loop:
        # count_l is nums[:i]
        # We want to update it so that for the next iteration (i+1),
        # count_l will be nums[:i+1].
        # So we increment count_l[nums[i]].

        # Let's re-calculate sum_sq_L correctly.
        # Before: sum_sq_L = sum(count_l[v]^2)
        # After adding 1 to count_l[c]:
        # new_sum_sq_L = sum_sq_L - (old_count_l[c])^2 + (old_count_l[c] + 1)^2
        # old_count_l[c] is cur_lc.

        # Wait, I already used cur_lc to calculate ways.
        # So:
        sum_sq_L = sum_sq_L - (cur_lc**2) + ((cur_lc + 1)**2)

    return ans
