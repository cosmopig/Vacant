import math

def binom_p(k, n):
    # Probability of getting at least k successes in n trials (p=0.5)
    # P(X >= k) = sum_{i=k}^{n} C(n, i) * 0.5^n
    prob = 0
    for i in range(k, n + 1):
        prob += math.comb(n, i)
    return prob * (0.5**n)

# X: REJECTs on BAD side (X=15/16)
p_x = binom_p(15, 16)
print(f"P(X>=15): {p_x}")

# Y: ACCEPTs on GOOD side (Y=7/15)
p_y = binom_p(7, 15)
print(f"P(Y>=7): {p_y}")
