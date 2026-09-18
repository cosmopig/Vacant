def pin(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must not be above hi")
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
