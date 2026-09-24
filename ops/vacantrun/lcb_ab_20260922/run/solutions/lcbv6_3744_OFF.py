def d(x):
    if x == 0:
        return 0
    k = 0
    while x > 0:
        x //= 4
        k += 1
    return k

PRECOMPUTED_SUMS = [0] * 20
for K in range(1, 20):
    s = 0
    for k in range(1, K):
        s += 3 * k * (4**(k-1))
    PRECOMPUTED_SUMS[K] = s

def P(X):
    if X <= 0:
        return 0
    K = d(X)
    return PRECOMPUTED_SUMS[K] + K * (X - 4**(K-1) + 1)

def minOperations(queries):
    total_sum = 0
    for l, r in queries:
        S = P(r) - P(l-1)
        M = d(r)
        total_sum += max((S + 1) // 2, M)
    return total_sum
