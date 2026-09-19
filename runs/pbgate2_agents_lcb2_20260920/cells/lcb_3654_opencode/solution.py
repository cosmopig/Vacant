from typing import List

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    # dp[i][j] is the minimum sum using i of op1 and j of op2
    # Initialize with a very large number
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0
    
    for x in nums:
        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        
        # Possible operations for this x:
        # Each entry is (reduction, op1_used, op2_used)
        options = []
        
        # Option 0: No operations
        options.append((0, 0, 0))
        
        # Option 1: Op 1 only
        v1 = (x + 1) // 2
        options.append((x - v1, 1, 0))
        
        # Option 2: Op 2 only
        if x >= k:
            options.append((k, 0, 1))
            
        # Option 3: Both
        # Order 1 then 2
        v_temp = (x + 1) // 2
        if v_temp >= k:
            res_12 = v_temp - k
            options.append((x - res_12, 1, 1))
        
        # Order 2 then 1
        if x >= k:
            v_temp2 = x - k
            res_21 = (v_temp2 + 1) // 2
            options.append((x - res_21, 1, 1))
            
        # Update new_dp based on current dp and options
        for i in range(op1 + 1):
            for j in range(op2 + 1):
                if dp[i][j] == float('inf'):
                    continue
                
                for red, u1, u2 in options:
                    ni, nj = i + u1, j + u2
                    if ni <= op1 and nj <= op2:
                        if dp[i][j] + red < new_dp[ni][nj]:
                            new_dp[ni][nj] = dp[i][j] + red
        dp = new_dp

    return int(min(min(row) for row in dp))
