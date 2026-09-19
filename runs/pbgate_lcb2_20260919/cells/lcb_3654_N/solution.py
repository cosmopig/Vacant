from typing import List
import math

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    # For each number, we have 4 possible states:
    # 0. No operation
    # 1. Operation 1 only (divide by 2, round up)
    # 2. Operation 2 only (subtract k if >= k)
    # 3. Both operations (Operation 1 then Operation 2 OR Operation 2 then Operation 1)

    n = len(nums)
    # dp[j][l] is the minimum sum using some prefix of nums with j op1 and l op2 used.
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0

    for x in nums:
        v0 = x
        v1 = math.ceil(x / 2)
        v2 = x - k if x >= k else x
        
        # Both options for (1, 1) cost
        val_a = v1
        if val_a >= k: val_a -= k
        
        val_b = x - k if x >= k else x
        val_b = math.ceil(val_b / 2)
        v3 = min(val_a, val_b)

        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if dp[j][l] == float('inf'):
                    continue
                
                # Option 0: No ops
                new_dp[j][l] = min(new_dp[j][l], dp[j][l] + v0)
                
                # Option 1: Op1 only
                if j + 1 <= op1:
                    new_dp[j+1][l] = min(new_dp[j+1][l], dp[j][l] + v1)
                
                # Option 2: Op2 only
                if l + 1 <= op2:
                    new_dp[j][l+1] = min(new_dp[j][l+1], dp[j][l] + v2)
                
                # Option 3: Both
                if j + 1 <= op1 and l + 1 <= op2:
                    new_dp[j+1][l+1] = min(new_dp[j+1][l+1], dp[j][l] + v3)
        dp = new_dp

    ans = float('inf')
    for j in range(op1 + 1):
        for l in range(op2 + 1):
            ans = min(ans, dp[j][l])
    return int(ans)
