from typing import List

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    n = len(nums)
    # dp[i][j] is the minimum sum using i of Op1 and j of Op2
    # Initialize with a very large value
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0

    for x in nums:
        v0 = x
        v1 = (x + 1) // 2
        v2 = x - k if x >= k else x
        
        # Both operations applied to the same index
        # Option A: Op1 then Op2
        res_a = v1 - k if v1 >= k else v1
        # Option B: Op2 then Op1
        res_b = (x - k + 1) // 2 if x >= k else x
        v12 = min(res_a, res_b)

        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        for i in range(op1 + 1):
            for j in range(op2 + 1):
                if dp[i][j] == float('inf'):
                    continue
                
                # Choice 0: No operations
                new_dp[i][j] = min(new_dp[i][j], dp[i][j] + v0)
                
                # Choice 1: Only Op1
                if i + 1 <= op1:
                    new_dp[i+1][j] = min(new_dp[i+1][j], dp[i][j] + v1)
                
                # Choice 2: Only Op2
                if j + 1 <= op2:
                    new_dp[i][j+1] = min(new_dp[i][j+1], dp[i][j] + v2)
                
                # Choice 3: Both Op1 and Op2
                if i + 1 <= op1 and j + 1 <= op2:
                    new_dp[i+1][j+1] = min(new_dp[i+1][j+1], dp[i][j] + v12)
        dp = new_dp

    ans = float('inf')
    for i in range(op1 + 1):
        for j in range(op2 + 1):
            ans = min(ans, dp[i][j])
    return int(ans)
