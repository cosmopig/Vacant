from typing import List
import math

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    n = len(nums)
    # dp[j][l] is the minimum sum using j Op1 and l Op2.
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0
    
    for x in nums:
        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        
        # Possible values after operations on current element x
        v0 = x
        v1 = math.ceil(x / 2)
        v2 = (x - k) if x >= k else float('inf')
        
        best_v_both = float('inf')
        # Order A: Op 1 then Op 2
        resA = math.ceil(x / 2)
        if resA >= k:
            best_v_both = min(best_v_both, resA - k)
        # Order B: Op 2 then Op 1
        if x >= k:
            resB = math.ceil((x - k) / 2)
            best_v_both = min(best_v_both, resB)
            
        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if dp[j][l] == float('inf'):
                    continue
                
                # Option 0: No operation on x
                new_dp[j][l] = min(new_dp[j][l], dp[j][l] + v0)
                
                # Option 1: Op 1 only on x
                if j + 1 <= op1:
                    new_dp[j+1][l] = min(new_dp[j+1][l], dp[j][l] + v1)
                
                # Option 2: Op 2 only on x
                if l + 1 <= op2 and v2 != float('inf'):
                    new_dp[j][l+1] = min(new_dp[j][l+1], dp[j][l] + v2)

                # Option 3: Both operations on x
                if j + 1 <= op1 and l + 1 <= op2 and best_v_both != float('inf'):
                    new_dp[j+1][l+1] = min(new_dp[j+1][l+1], dp[j][l] + best_v_both)

        dp = new_dp

    ans = float('inf')
    for j in range(op1 + 1):
        for l in range(op2 + 1):
            ans = min(ans, dp[j][l])
            
    return int(ans)
