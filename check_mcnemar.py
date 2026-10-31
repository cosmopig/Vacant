import math
from e006_opencode_polyglot_recompute import mcnemar

def test():
    # Try to find (a, c) such that mcnemar(a, c) == 0.625
    for a in range(100):
        for c in range(100):
            p = mcnemar(a, c)
            if abs(p - 0.625) < 1e-6:
                print(f"Found: a={a}, c={c}, p={p}")

test()
