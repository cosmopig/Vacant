from typing import List
import math

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    # We want to maximize the total reduction in sum.
    # For each index i, we have 4 choices (since operations are at most once per index):
    # 0. No operation: reduction = 0
    # 1. Op1 only: reduction = nums[i] - math.ceil(nums[i] / 2)
    # 2. Op2 only: reduction = k if nums[i] >= k else 0
    # 3. Both Op1 and Op2: reduction = nums[i] - min_result_after_both

    reductions = []
    for x in nums:
        r1 = x - math.ceil(x / 2)
        r2 = k if x >= k else 0

        # Both operations (order matters for the result, we want the best one)
        # Option A: Op1 then Op2
        v_a = math.ceil(x / 2)
        res_a = v_a - k if v_a >= k else v_a
        r3_a = x - res_a

        # Option B: Op2 then Op1
        if x >= k:
            v_b = math.ceil((x - k) / 2)
            res_b = v_b
            r3_b = x - res_b
        else:
            r3_b = 0 # Cannot apply Op2 if x < k

        r3 = max(r3_a, r3_b)
        reductions.append((r1, r2, r3))

    # DP state: dp[i][j] is the maximum reduction using i units of op1 and j units of op2
    dp = [[-1] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0

    for r1, r2, r3 in reductions:
        # We iterate backwards to update the DP table in place or use a new one.
        # Using a new one is safer/clearer for this logic.
        new_dp = [row[:] for row in dp]
        for i in range(op1 + 1):
            for j in range(op2 + 1):
                if dp[i][j] == -1: continue

                # Option 1: Use Op1 only (cost 1 op1)
                if i + 1 <= op1:
                    new_dp[i+1][j] = max(new_dp[i+1][j], dp[i][j] + r1)
                # Option 2: Use Op2 only (cost 1 op2)
                if j + 1 <= op2:
                    new_dp[i][j+1] = max(new_dp[i][j+1], dp[i][j] + r2)
                # Option 3: Use both (cost 1 op1, 1 op2)
                if i + 1 <= op1 and j + 1 <= op2:
                    new_dp[i+1][j+1] = max(new_dp[i+1][j+1], dp[i][j] + r3)
        dp = new_dp

    max_reduction = 0
    for i in range(op1 + 1):
        for j in range(op2 + 1):
            if dp[i][j] != -1:
                max_reduction = max(max_reduction, dp[i][j])

    return sum(nums) - max_reduction
