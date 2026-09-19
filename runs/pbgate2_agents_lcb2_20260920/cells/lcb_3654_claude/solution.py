from typing import List
import math

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    # Each element can have 4 states:
    # 0: No operation
    # 1: Operation 1 only (divide by 2, round up)
    # 2: Operation 2 only (subtract k if >= k)
    # 3: Both operations (Operation 1 then Operation 2 OR Operation 2 then Operation 1)

    # Since we want to minimize the sum, for each index i, we calculate the possible values:
    # v0 = nums[i]
    # v1 = math.ceil(nums[i] / 2)
    # v2 = nums[i] - k if nums[i] >= k else nums[i]
    # v3_a = math.ceil((nums[i] / 2) / 2) -- wait, the rule says "at most once each"
    # Let's re-read:
    # Op1: divide by 2, round up (max op1 times total, max once per index)
    # Op2: subtract k if >= k (max op2 times total, max once per index)
    # Both can be applied to the same index, but at most once each.

    # So for a single index i:
    # Option A: No ops -> nums[i]
    # Option B: Op1 only -> ceil(nums[i] / 2)
    # Option C: Op2 only -> nums[i] - k (if >= k, else nums[i])
    # Option D: Both -> ceil((nums[i] - k) / 2) if nums[i] >= k else ceil(nums[i] / 2) - k?
    # Wait, "Both operations can be applied to the same index". Does order matter?
    # If I do Op1 then Op2: ceil(nums[i]/2) - k (if ceil(nums[i]/2) >= k)
    # If I do Op2 then Op1: ceil((nums[i]-k)/2) if nums[i] >= k else ...
    # Actually, the problem says "Return the minimum possible sum".
    # For a fixed index i, we want to know the best reduction.
    # But there are global limits op1 and op2. This is a dynamic programming or greedy problem?
    # Since we have two independent resources (op1 and op2), but they can interact on the same element.

    # Let's refine the options for each index i:
    # 1. No ops: cost_op1=0, cost_op2=0, value = nums[i]
    # 2. Op1 only: cost_op1=1, cost_op2=0, value = (nums[i] + 1) // 2
    # 3. Op2 only: cost_op1=0, cost_op2=1, value = nums[i] - k if nums[i] >= k else nums[i]
    # 4. Both: cost_op1=1, cost_op2=1, value = min( (nums[i]+1)//2 - k if (nums[i]+1)//2 >= k else (nums[i]+1)//2, (nums[i]-k+1)//2 if nums[i] >= k else ... )
    # Actually, for "Both", we just want the minimum of:
    #   - Op1 then Op2: val = (nums[i]+1)//2; if val >= k: val -= k
    #   - Op2 then Op1: val = nums[i] - k (if nums[i] >= k); val = (val+1)//2
    # Wait, the problem says "Both operations can be applied to the same index".
    # It doesn't say they must be independent. If I apply both, I use 1 of op1 and 1 of op2.
    # The resulting value is min(Op1 then Op2, Op2 then Op1).

    # This looks like a variation of the knapsack problem or a flow problem, but since n is small (100),
    # we can use DP.
    # dp[i][j][l] = min sum using first i elements with j op1 and l op2 used.
    # But wait, the number of operations is up to 100.
    # dp[op1_used][op2_used] = min sum.
    # We iterate through each number and update the DP table.

    n = len(nums)
    # dp[j][l] is the minimum sum using j op1s and l op2s
    # Initialize with infinity
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = sum(nums)

    # Actually, it's easier to think about the "reduction" we get.
    # For each nums[i], we have 4 choices:
    # (delta_op1, delta_op2, reduction)
    # Choice 0: (0, 0, 0)
    # Choice 1: (1, 0, nums[i] - (nums[i]+1)//2)  -- only if op1 > 0
    # Choice 2: (0, 1, nums[i] - (nums[i]-k if nums[i] >= k else nums[i])) -- only if op2 > 0
    # Choice 3: (1, 1, nums[i] - min_val_with_both) -- only if op1 > 0 and op2 > 0

    # Let's pre-calculate reductions for each index.
    reductions = []
    for x in nums:
        r0 = 0
        r1 = x - (x + 1) // 2
        r2 = x - (x - k if x >= k else x)
        # For both, we want the best order.
        # Order 1 then 2:
        v_a = (x + 1) // 2
        if v_a >= k: v_a -= k
        res_a = x - v_a
        # Order 2 then 1:
        v_b = x - k if x >= k else x
        v_b = (v_b + 1) // 2
        res_b = x - v_b
        r3 = max(res_a, res_b) # We want maximum reduction
        reductions.append((0, 0, r0, r1, r2, r3))

    # dp[j][l] = min sum using j op1 and l op2
    # Since we process one number at a time, we need to update the table.
    # To avoid using the same element twice, we iterate backwards or use a new table.

    current_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    current_dp[0][0] = sum(nums)

    for i in range(n):
        r0, r1, r2, r3 = reductions[i][0], reductions[i][1], reductions[i][2], reductions[i][3]
        next_dp = [row[:] for row in current_dp]
        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if current_dp[j][l] == float('inf'): continue

                # Option 1: Op1 only
                if j + 1 <= op1:
                    next_dp[j+1][l] = min(next_dp[j+1][l], current_dp[j][l] - r1)
                # Option 2: Op2 only
                if l + 1 <= op2:
                    next_dp[j][l+1] = min(next_dp[j][l+1], current_dp[j][l] - r2)
                # Option 3: Both
                if j + 1 <= op1 and l + 1 <= op2:
                    next_dp[j+1][l+1] = min(next_dp[j+1][l+1], current_dp[j][l] - r3)
        current_dp = next_dp

    ans = float('inf')
    for j in range(op1 + 1):
        for l in range(op2 + 1):
            ans = min(ans, current_dp[j][l])
    return int(ans)
