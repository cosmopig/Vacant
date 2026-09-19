from typing import List

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    # dp[j][l] is the minimum sum of elements processed so far using j op1 and l op2.
    n = len(nums)
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0

    for x in nums:
        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        r0 = x
        r1 = (x + 1) // 2
        r2 = x - k if x >= k else x
        # For both, we want the minimum possible value.
        v_a = r1 - k if r1 >= k else r1
        v_b = (x - k + 1) // 2 if x >= k else x
        r3 = min(v_a, v_b)

        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if dp[j][l] == float('inf'):
                    continue
                
                # Option 0: No op
                new_dp[j][l] = min(new_dp[j][l], dp[j][l] + r0)
                
                # Option 1: Op1
                if j + 1 <= op1:
                    new_dp[j+1][l] = min(new_dp[j+1][l], dp[j][l] + r1)
                
                # Option 2: Op2
                if l + 1 <= op2:
                    new_dp[j][l+1] = min(new_dp[j][l+1], dp[j][l] + r2)
                
                # Option 3: Both
                if j + 1 <= op1 and l + 1 <= op2:
                    new_dp[j+1][l+1] = min(new_dp[j+1][l+1], dp[j][l] + r3)
        dp = new_dp

    ans = float('inf')
    for j in range(op1 + 1):
        for l in range(op2 + 1):
            ans = min(ans, dp[j][l])
    return int(ans)
