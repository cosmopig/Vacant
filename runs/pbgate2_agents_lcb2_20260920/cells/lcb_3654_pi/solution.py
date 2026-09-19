from typing import List

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    n = len(nums)
    # dp[j][l] is the minimum sum using j Op1 and l Op2
    # Initialize with a very large value
    inf = float('inf')
    dp = [[inf] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0

    for x in nums:
        next_dp = [[inf] * (op2 + 1) for _ in range(op1 + 1)]
        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if dp[j][l] == inf:
                    continue
                
                current_sum = dp[j][l]
                
                # Option 0: No operation
                if current_sum + x < next_dp[j][l]:
                    next_dp[j][l] = current_sum + x
                
                # Option 1: Op1 only
                if j + 1 <= op1:
                    v1 = (x + 1) // 2
                    if current_sum + v1 < next_dp[j+1][l]:
                        next_dp[j+1][l] = current_sum + v1
                
                # Option 2: Op2 only
                if l + 1 <= op2 and x >= k:
                    v2 = x - k
                    if current_sum + v2 < next_dp[j][l+1]:
                        next_dp[j][l+1] = current_sum + v2
                
                # Option 3: Both operations
                if j + 1 <= op1 and l + 1 <= op2:
                    # Op1 then Op2
                    v1 = (x + 1) // 2
                    res_a = v1 - k if v1 >= k else v1
                    
                    # Op2 then Op1
                    res_b = inf
                    if x >= k:
                        v2 = x - k
                        res_b = (v2 + 1) // 2
                    
                    best_both = min(res_a, res_b)
                    if current_sum + best_both < next_dp[j+1][l+1]:
                        next_dp[j+1][l+1] = current_sum + best_both
        dp = next_dp

    ans = inf
    for j in range(op1 + 1):
        for l in range(op2 + 1):
            if dp[j][l] < ans:
                ans = dp[j][l]
    return int(ans)
