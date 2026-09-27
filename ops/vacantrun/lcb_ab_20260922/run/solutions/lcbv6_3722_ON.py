def maxSum(nums, k, m):
    n = len(nums)
    S = [0] * (n + 1)
    for i in range(n):
        S[i+1] = S[i] + nums[i]

    # dp[j][i] is the max sum of j non-overlapping subarrays using first i elements.
    dp = [[float('-inf')] * (n + 1) for _ in range(k + 1)]
    
    # Base case: 0 subarrays have sum 0 for any number of elements.
    for i in range(n + 1):
        dp[0][i] = 0

    for j in range(1, k + 1):
        M = [float('-inf')] * (n + 1)
        for i in range(n + 1):
            M[i] = dp[j-1][i] - S[i]
        
        # Compute prefix maximums for M
        for i in range(1, n + 1):
            if M[i-1] > M[i]:
                M[i] = M[i-1]

        for i in range(m, n + 1):
            res = S[i] + M[i - m]
            if i > m:
                dp[j][i] = max(dp[j][i-1], res)
            else:
                dp[j][i] = res

    return dp[k][n]
