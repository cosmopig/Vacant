from typing import List
import math

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    # For each number, there are 4 possible states:
    # 0. No operation
    # 1. Operation 1 only (divide by 2, round up)
    # 2. Operation 2 only (subtract k if >= k)
    # 3. Both operations (order doesn't matter for the final value, but we need to check both sequences)
    
    # Actually, since we want minimum sum and each operation can be used at most once per index:
    # Let v = nums[i]
    # Option A: v
    # Option B: ceil(v / 2)
    # Option C: max(0, v - k) if v >= k else v
    # Option D1 (Op1 then Op2): v' = ceil(v / 2), result = max(0, v' - k) if v' >= k else v'
    # Option D2 (Op2 then Op1): v'' = max(0, v - k) if v >= k else v, result = ceil(v'' / 2)
    
    options = []
    for v in nums:
        opt_none = v
        opt_op1 = math.ceil(v / 2)
        opt_op2 = max(0, v - k) if v >= k else v
        
        # Op1 then Op2
        v_after_op1 = math.ceil(v / 2)
        opt_both_1 = max(0, v_after_op1 - k) if v_after_op1 >= k else v_after_op1
        
        # Op2 then Op1
        v_after_op2 = max(0, v - k) if v >= k else v
        opt_both_2 = math.ceil(v_after_op2 / 2)
        
        options.append({
            'none': opt_none,
            'op1': opt_op1,
            'op2': opt_op2,
            'both': min(opt_both_1, opt_both_2)
        })

    # This is a variation of the knapsack problem / dynamic programming.
    # We want to pick at most op1 indices for Op1 and op2 indices for Op2.
    # However, an index can be used for both.
    # Let's rephrase: 
    # Each index i can be in one of 4 states:
    # State 0: None (cost: 0 op1, 0 op2) -> value opt_none
    # State 1: Op1 only (cost: 1 op1, 0 op2) -> value opt_op1
    # State 2: Op2 only (cost: 0 op1, 1 op2) -> value opt_op2
    # State 3: Both (cost: 1 op1, 1 op2) -> value opt_both

    # dp[i][j] = min sum using i of op1 and j of op2
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0
    
    for opt in options:
        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        for i in range(op1 + 1):
            for j in range(op2 + 1):
                if dp[i][j] == float('inf'):
                    continue
                
                # Option: None
                new_dp[i][j] = min(new_dp[i][j], dp[i][j] + opt['none'])
                
                # Option: Op1 only
                if i + 1 <= op1:
                    new_dp[i+1][j] = min(new_dp[i+1][j], dp[i][j] + opt['op1'])
                
                # Option: Op2 only
                if j + 1 <= op2:
                    new_dp[i][j+1] = min(new_dp[i][j+1], dp[i][j] + opt['op2'])
                
                # Option: Both
                if i + 1 <= op1 and j + 1 <= op2:
                    new_dp[i+1][j+1] = min(new_dp[i+1][j+1], dp[i][j] + opt['both'])
        dp = new_dp

    ans = float('inf')
    for i in range(op1 + 1):
        for j in range(op2 + 1):
            ans = min(ans, dp[i][j])
            
    return int(ans)
