from typing import List

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    n = len(nums)
    # dp[j][l] is the minimum sum using j Op1 and l Op2
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0
    
    for x in nums:
        v00 = x
        v10 = (x + 1) // 2
        
        v01 = float('inf')
        if x >= k:
            v01 = x - k
        
        v11 = float('inf')
        # Option A: Op1 then Op2
        val_a = (x + 1) // 2
        if val_a >= k:
            v11 = min(v11, val_a - k)
        # Option B: Op2 then Op1
        if x >= k:
            val_b = (x - k + 1) // 2
            v11 = min(v11, val_b)
            
        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if dp[j][l] == float('inf'):
                    continue
                
                # Option (0,0)
                if new_dp[j][l] > dp[j][l] + v00:
                    new_dp[j][l] = dp[j][l] + v00
                
                # Option (1,0)
                if j + 1 <= op1:
                    if new_dp[j+1][l] > dp[j][l] + v10:
                        new_dp[j+1][l] = dp[j][l] + v10
                
                # Option (0,1)
                if l + 1 <= op2 and v01 != float('inf'):
                    if new_dp[j][l+1] > dp[j][l] + v01:
                        new_dp[j][l+1] = dp[j][l] + v01
                
                # Option (1,1)
                if j + 1 <= op1 and l + 1 <= op2 and v11 != float('inf'):
                    if new_dp[j+1][l+1] > dp[j][l] + v11:
                        new_dp[j+1][l+1] = dp[j][l] + v11
        dp = new_dp

    return int(min(min(row) for row in dp))
