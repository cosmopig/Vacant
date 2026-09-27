import math

def minimumIncrements(nums, target):
    n = len(target)
    
    def get_lcm(a, b):
        if a == 0 or b == 0:
            return 0
        return abs(a * b) // math.gcd(a, b)

    lcms = [1] * (1 << n)
    for i in range(1, 1 << n):
        current_lcm = 1
        for j in range(n):
            if (i >> j) & 1:
                t = target[j]
                current_lcm = get_lcm(current_lcm, t)
        lcms[i] = current_lcm

    min_costs = [float('inf')] * (1 << n)
    for i in range(1, 1 << n):
        lcm_val = lcms[i]
        best = float('inf')
        for x in nums:
            cost = ((x + lcm_val - 1) // lcm_val) * lcm_val - x
            if cost < best:
                best = cost
        min_costs[i] = best

    dp = [float('inf')] * (1 << n)
    dp[0] = 0
    for mask in range(1, 1 << n):
        s = mask
        while s > 0:
            if min_costs[s] != float('inf'):
                res = min_costs[s] + dp[mask ^ s]
                if res < dp[mask]:
                    dp[mask] = res
            s = (s - 1) & mask
            
    return int(dp[(1 << n) - 1])
