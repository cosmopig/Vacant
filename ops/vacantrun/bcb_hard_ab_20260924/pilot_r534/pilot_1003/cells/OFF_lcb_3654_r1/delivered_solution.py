from typing import List

def minArraySum(nums: List[int], k: int, op1: int, op2: int) -> int:
    n = len(nums)
    # The maximum number of operations we can actually use is n.
    # However, the constraints say op1, op2 <= n.
    # dp[j][l] is the minimum sum using j of Op 1 and l of Op 2.
    dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
    dp[0][0] = 0

    for x in nums:
        new_dp = [[float('inf')] * (op2 + 1) for _ in range(op1 + 1)]
        
        # Options for this element: (op1_used, op2_used, value)
        options = []
        # Option 0: No operations
        options.append((0, 0, x))
        
        # Option 1: Op 1 only
        v10 = (x + 1) // 2
        options.append((1, 0, v10))
        
        # Option 2: Op 2 only
        if x >= k:
            v01 = x - k
            options.append((0, 1, v01))
            
        # Option 3: Both ops
        v11 = float('inf')
        # Order 1: Op 1 then Op 2
        v_temp1 = (x + 1) // 2
        if v_temp1 >= k:
            v11 = min(v11, v_temp1 - k)
        # Order 2: Op 2 then Op 1
        if x >= k:
            v_temp2 = (x - k + 1) // 2
            v11 = min(v11, v_temp2)
        
        if v11 != float('inf'):
            options.append((1, 1, v11))

        for j in range(op1 + 1):
            for l in range(op2 + 1):
                if dp[j][l] == float('inf'):
                    continue
                
                for op1_used, op2_used, val in options:
                    nj = j + op1_used
                    nl = l + op2_used
                    if nj <= op1 and nl <= op2:
                        if dp[j][l] + val < new_dp[nj][nl]:
                            new_dp[nj][nl] = dp[j][l] + val
        dp = new_dp

    ans = float('inf')
    for j in range(op1 + 1):
        for l in range(op2 + 1):
            if dp[j][l] < ans:
                ans = dp[j][l]
    return int(ans)
